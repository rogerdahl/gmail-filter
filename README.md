# Add filters in Gmail

This is essentially a convenient shortcut that enables creating simple filters in Gmail from the command line. The same actions can be performed manually in the Gmail web app.

The command takes email addresses or domains along with labels, and creates filters that apply those labels to emails sent from the given email addresses or domains.



## Setup
 
```shell
pip install -r requirements.txt
```

* This uses the Google Gmail API. For it to work, the Gmail API must be enabled for the Gmail account for which this will be used (this used to be a major hassle but is now quick and easy). 

* On first run, a login window will open, in which you have to log in and click Ok on
  a number of scary warnings from Google about unverified programs.


## Usage:

```shell
usage: gmail-filter.py [-h] [--debug] [--include-untagged] {add,file,filters,labels,clear,test} ...

positional arguments:
  {add,file,filters,labels,clear,test}
    add                 Add emails to label
    file                Add emails from file to label
    filters             List email filters
    clear               Delete filters created by this program
    test                Automatically add some bogus filters for testing

optional arguments:
  -h, --help            show this help message and exit
  --debug               Debug level logging
  --include-untagged    Include filters and labels not created by this program
```

## Notes

* The only actions performed by the generated filters is to remove the `INBOX` label and add a user label to incoming emails that match. The generated filters are equivalent to filters created manually with `Skip the inbox` checked, and the given label set in `Apply the label: ___`.

* When adding a new email address, the program first searches filters for a filter that matches the email address and that uses the label specified with `--label` (with fallback to default if none is specified). 
  
  If an existing filter is not found, a new filter is created. If the new filter needs a label that does not exist, the label is created as well.   

  The new email is then added to the filter that was found or created.

* The program ignores filters not created by itself, both in read and write operations. It tracks and recognizes its filters by adding a "tag" to the labels that it creates.
  
* As of early 2021:

  * Unless there are changes in the last year or two, the only two types of email addresses supported in Gmail filters are on the form, `account@domain.tld` (matching an exact mailbox), and `domain.tld` (matching all mailboxes in a given domain). Note that the latter does not include the `@`.

  * Creating filters manually is only supported in the Gmail web app, not the Android or iOS apps.
    
  * Gmail allows up to 1000 separate filters (each of which perhaps 50 email addresses). 

## TODO

* The program adds emails one at a time. Checks for each email takes several round-trips to Gmail, so it takes around 1 second per email. So, adding large numbers of emails is going to be slow and may run into call limits that Google has set for free use of the Gmail API as well. It's possible to speed this up by orders of magnitude for "bulk" operations by adding a whole list of emails at a time, and doing smarter checks on the whole list up front.
