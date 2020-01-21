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
    soup = bs4.BeautifulSoup(resp.get_data(), 'html.parser')

    # Get CSRF hash.
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
    if csrf is None:
        print('Failed to find CSRF token')
        return False

    # Get hash from "Enter Raffle" button.
    hash = None
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

        # Parse all open raffles not yet entered.
        # We parse the available raffles in reverse as to enter the oldest raffles first.
        soup = bs4.BeautifulSoup(resp.get_data(), 'html.parser')
        for raffle in reversed(soup.find_all('div', {'class': 'panel-raffle'})):
            # Ignore raffles which have already been entered.
            if 'raffle-entered' in raffle.get('class'):
                continue
            raffle_id = raffle.get('id').split('-')[-1]
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
