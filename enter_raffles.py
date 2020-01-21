#!/usr/bin/env python3

import bs4
import http.cookiejar
import json
import mechanize
import os
from time import sleep

COOKIES_PATH = 'cookies.txt'
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/79.0.3945.79 Chrome/79.0.3945.79 Safari/537.36'

# Delay between raffle entries in seconds.
DELAY = 5

def get_csrf_hash(resp):
    """
    Gets the CSRF hash for the given page.

    Args:
        A mechanize.Response response representing the returned page.

    Returns:
        The CSRF token if it is found, and None otherwise.
    """
    soup = bs4.BeautifulSoup(resp.get_data(), 'html.parser')
    csrf = None
    for script in soup.find_all('script'):
        content = script.text
        # Check if code sets our CSRF hash.
        pos = content.find('ScrapTF.User.Hash')
        if pos == -1:
            continue
        begin = content.find('=', pos) + 1
        end = content.find('\n', begin) - 1
        csrf = content[begin:end].replace('"', '').strip()
    return csrf

def try_enter_raffle(br, raffle_id):
    """
    Attempts to enter a raffle.

    Args:
        br: http.cookiejar.Browser to open raffle web page with.
        raffle_id: The raffle ID (case-insensitive)

    Returns:
        True on success, False otherwise.
    """
    FORM_URL = 'https://scrap.tf/ajax/viewraffle/EnterRaffle'
    raffle_id = raffle_id.upper()

    print('Attempting to enter raffle {}...'.format(raffle_id))

    url = 'https://scrap.tf/raffles/{}'.format(raffle_id)
    resp = br.open(url)

    # Get CSRF hash.
    csrf = get_csrf_hash(resp)
    if csrf is None:
        print('Failed to find CSRF token')
        return False

    # Get hash from "Enter Raffle" button.
    soup = bs4.BeautifulSoup(resp.get_data(), 'html.parser')
    button = soup.find('button', {'id': 'raffle-enter'})
    onclick = button.get('onclick')
    begin = onclick.find('(') + 1
    end = onclick.find(')', begin) - 1
    button_args = onclick[begin:end].replace('\'', '').split(',')
    raffle_hash = button_args[1].strip()

    # Send form request.
    post_data = {
        'raffle': raffle_id,
        'hash': raffle_hash,
        'csrf': csrf
    }
    req = mechanize.Request(FORM_URL, data=post_data)
    resp = br.open(req)

    # Interpret JSON response
    json_resp = json.loads(resp.get_data())
    print(json_resp['message'])

    success = json_resp['success']
    if type(success) == bool:
        return success
    else:
        return False

def get_raffle_batch(br, csrf, raffle_id=''):
    """
    Gets a batch of open raffles whose start date precedes a given raffle.

    Args:
        br: http.cookiejar.Browser to call requests from.
        csrf: CSRF hash of main raffle page.
        raffle_id: ID of raffle to get raffles after (exclusive).

    Returns:
        List of tuples (`new_raffle_id`, `entered`) where `entered` is a boolean
        of whether the associated raffle has already been entered. This list is
        followed by a boolean of whether there are more raffles preceding the
        last raffle ID. Tuples are in chronological order from newest to oldest.

        False is returned on failure.
    """
    PAGINATE_URL = 'https://scrap.tf/ajax/raffles/Paginate'

    # Call the Paginate AJAX query on Scrap.tf.
    post_data = {
        'start': raffle_id,
        'sort': 0,
        'puzzle': 0,
        'csrf': csrf
    }
    req = mechanize.Request(PAGINATE_URL, data=post_data)
    resp = br.open(req)

    # Interpret JSON response.
    json_resp = json.loads(resp.get_data())
    success = json_resp['success']
    if not success:
        return False

    # Parse HTML to obtain raffle IDs.
    raffles = []
    soup = bs4.BeautifulSoup(json_resp['html'], 'html.parser')
    for raffle in soup.find_all('div', {'class': 'panel-raffle'}):
        # Ignore raffles which have already been entered.
        entered = 'raffle-entered' in raffle.get('class')
        raffle_id = raffle.get('id').split('-')[-1]
        raffles.append((raffle_id, entered))

    return raffles, json_resp['done']

def get_all_raffles(br, csrf):
    """
    Gets all public raffles

    Args:
        br: http.cookiejar.Browser to call requests from.
        csrf: CSRF hash of main raffle page.

    Returns:
        List of tuples (`new_raffle_id`, `entered`) where `entered` is a boolean
        of whether the associated raffle has already been entered. Tuples are
        in chronological order from newest to oldest.

        False is returned on failure.
    """
    lastid = ''
    raffles = []
    done = False
    while not done:
        resp = get_raffle_batch(br, csrf, lastid)
        if not resp:
            return False

        batch, done = resp
        raffles += batch
        lastid = raffles[-1][0]
    return raffles

def try_enter_all_raffles(br):
    """
    Enters unentered raffles until a bad response is encountered.
    This function may be safely interrupted.

    Args:
        br: http.cookiejar.Browser to open raffle web pages with.

    Returns:
        Number of raffles successfully entered.
    """
    entered_cnt = 0

    try:
        # Fetch page containing open raffles.
        resp = br.open('https://scrap.tf/raffles')

        # Get CSRF hash.
        csrf = get_csrf_hash(resp)
        if csrf is None:
            print('Failed to find CSRF token on main page')
            return False

        # Get all active raffles.
        raffles = get_all_raffles(br, csrf)

        # Parse all raffles not yet entered.
        # We parse the available raffles in reverse as to enter the oldest raffles first.
        for raffle_id, entered in reversed(raffles):
            # Ignore entered raffles.
            if entered:
                continue

            # Attempt to enter the raffle.
            if try_enter_raffle(br, raffle_id):
                entered_cnt += 1
            else:
                print('Failed to enter raffle {}'.format(raffle_id))
                break

            print('Waiting...')
            sleep(DELAY)
            print()

    except KeyboardInterrupt:
        print()
        print('Interrupt detected, halting script...')

    return entered_cnt

def main():
    # Configure browser
    br = mechanize.Browser()
    br.set_handle_equiv(True)
    br.set_handle_gzip(True)
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    br.set_handle_robots(False)
    br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

    # Load cookies.
    cj = http.cookiejar.LWPCookieJar()
    if os.path.exists(COOKIES_PATH):
        cj.load(COOKIES_PATH, ignore_discard=True, ignore_expires=True)
    br.set_cookiejar(cj)

    br.addheaders = [('User-agent', USER_AGENT)]

    entered_cnt = try_enter_all_raffles(br)
    print()
    print('Done')
    print('{} new raffles entered'.format(entered_cnt))

    # Save cookies.
    cj.save('cookies.txt', ignore_discard=True, ignore_expires=True)

if __name__ == '__main__':
    main()
