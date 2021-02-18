# Add email address to a Gmail filter

This uses the Google Gmail API to add an email address to a Gmail filter.

This allows adding email addresses to a specific filter in Gmail without having to
manually modify the filter in the Gmail web app.

I filter emails in Gmail because the filters in my local email client (Mozilla
Thunderbird) are buggy, and I don't want to manually log into Gmail and modify a filter
there every time one leaks through.

## Setup
 
```shell
./install.sh
```

* Enable the Gmail API for your Gmail account.

## Usage:

```shell
$ ./filter-from.py <acct@domain or @domain email address>
```

### Notes

* On first run, a login window will open, in which you have to log in and click Ok on
  scary warnings from Google about unverified scripts.

* The script looks for a filter in your Gmail account in which the first address in
  the `From` field is `spam@filter.invalid`. If not found, the script creates a new
  filter that has the required address in the `From` field, and
  actions, `Skip the inbox` and `Apply the label: from-spam`.

* The script then adds the new email address provided on the command list to the list of
  email addresses in the `From` field. The `From` address list is on the
  form, `addr OR addr OR ...`.

* The actions that are set up for the filter created by default can be modified at any
  time by going to `Settings > Filters and Blocked Addresses` in the Gmail web app.

* Email addresses on the form `account@domain.tld` and `domain.tld` (not including the `@`) have been tested. The latter will filter all email addresses from the given domain.

* Eventually, you may run out of room for more addresses in the `From` field. At that
  point, change `MAGIC_FILTER_ADDR` at the top of `filter-from.py`, and run the program
  again. This will trigger the creation of a new filter, and add the new email to it.

* As of early 2021:
    * Creating filters is only supported in the Gmai web app, not the Android or iOS
      apps.
    * Gmail allows up to 1000 separate filter (each of which can have at least 50 email
      addresses). 
