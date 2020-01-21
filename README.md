# Scrap.tf Auto Raffle Enterer

Utility for automatically entering public raffles on [Scrap.TF](https://scrap.tf/raffles).

## Requirements

 * Python 3.6 or higher
 * `mechanize` version 0.4.5 or higher

## Usage

 1. Login at [Scrap.TF](https://scrap.tf/raffles).
 2. Copy the cookie provided by Scrap.TF into `cookies.txt` in the LWP Perl format. If you are on Chrome, you may find the [EditThisCookie](http://www.editthiscookie.com/) plugin useful to this end.
 3. *(Optional)* Add a user agent to `user-agent.txt`.
 4. Run `./enter_raffles.py` in terminal.
