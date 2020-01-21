import bs4
import json
import mechanize
from time import sleep

MAIN_RAFFLE_URL = 'https://scrap.tf/raffles'

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

def get_num_raffles(br):
    """
    Get the number of raffles entered and the total number of raffles.

    Args:
        br: http.cookiejar.Browser to open raffle web page with.

    Returns:
        Number of raffles entered and the total number of raffles.
        False on failure.
    """
    resp = br.open(MAIN_RAFFLE_URL)
    soup = bs4.BeautifulSoup(resp.get_data(), 'html.parser')
    stat = soup.find('div', {'class': 'raffle-list-stat'})
    if stat is None:
        return False
    h1 = stat.find('h1')
    if h1 is None:
        return False
    entered, total = h1.text.split('/')
    return int(entered), int(total)

def try_enter_all_raffles(br, delay=5):
    """
    Enters unentered raffles. Termiantes if a bad response is encountered.
    This function may be safely interrupted.

    Args:
        br: http.cookiejar.Browser to open raffle web pages with.
        delay: Delay in seconds between requests.

    Returns:
        Number of raffles successfully entered.
    """
    new_entered_cnt = 0
    total_entered_cnt = 0

    try:
        # Fetch page containing open raffles.
        resp = br.open(MAIN_RAFFLE_URL)

        # Get CSRF hash.
        csrf = get_csrf_hash(resp)
        if csrf is None:
            print('Failed to find CSRF token on main page')
            return False

        # Get all active raffles.
        raffles = get_all_raffles(br, csrf)

        # Create list of unentered raffles.
        unentered = []
        for raffle_id, entered in reversed(raffles):
            if entered:
                total_entered_cnt += 1
            else:
                unentered.append(raffle_id)

        # Parse all unentered raffles.
        # We parse the available raffles in reverse as to enter the oldest raffles first.
        for i, raffle_id in enumerate(reversed(unentered)):
            # Attempt to enter the raffle.
            if try_enter_raffle(br, raffle_id):
                new_entered_cnt += 1
                total_entered_cnt += 1
            else:
                print('Failed to enter raffle {}'.format(raffle_id))
                break
            print('{}/{} raffles entered'.format(total_entered_cnt, len(raffles)))

            if i < len(unentered) - 1:
                print('Waiting...')
                sleep(delay)
            print()

    except KeyboardInterrupt:
        print()
        print('Interrupt detected, halting script...')

    return new_entered_cnt
