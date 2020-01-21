#!/usr/bin/env python3

import http.cookiejar
import mechanize
import os

from utils import get_num_raffles, try_enter_all_raffles

# File to load and save cookies from.
COOKIES_PATH = 'cookies.txt'

# File to look for user agent in.
USER_AGENT_PATH = 'user-agent.txt'

# Default user agent to use when none is provided.
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'

# Delay between raffle entries in seconds.
DELAY = 5


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

    # Load user agent from file.
    if os.path.exists(USER_AGENT_PATH):
        with open(USER_AGENT_PATH, 'r') as f:
            user_agent = f.readline().strip()
        print('Loaded user agent from file')
    else:
        user_agent = DEFAULT_USER_AGENT
        print('Using default user agent')
    br.addheaders = [('User-agent', user_agent)]
    print('User agent: {}'.format(user_agent))
    print()

    entered_cnt = try_enter_all_raffles(br, delay=DELAY)
    print('Done')
    print('{} raffles newly entered'.format(entered_cnt))

    try:
        num_resp = get_num_raffles(br)
        if num_resp is None:
            print('Could not load raffle stats')
        else:
            entered, total = num_resp
            print('{}/{} raffles entered'.format(entered, total))
    except KeyboardInterrupt:
        print('Canceled fetching of raffle stats')

    # Save cookies.
    cj.save('cookies.txt', ignore_discard=True, ignore_expires=True)

if __name__ == '__main__':
    main()
