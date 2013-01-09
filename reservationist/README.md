# reservationist.py
With Amazon's Consolidated Billing, a Reserved Instance purchased in one AWS account can have costs savings benefits applied to an instance matching the RI in any other consolidated billing account.

reservationish.py looks at AWS for currently running instances and active reserved instances over multiple accounts and regions and tells you were you need to buy reservations or, even worse, where you are over-reserved.

Some more information:
[Consolidated Billing & Reserved Instances](http://docs.amazonwebservices.com/awsaccountbilling/latest/about/consolidatedbilling.html#consolidatedbilling-ec2)
[Volume Discounts](http://docs.aws.amazon.com/awsaccountbilling/latest/about/consolidatedbilling.html#useconsolidatedbilling-discounts)

##### Defaults:
* It considers an instance "running" if it was created more than 7 days ago and is currently running
* Only counts a single offering type, defaults to "Heavy Utilization".

### Requirements
* python 2.6+
* boto
* one or more AWS accounts with Describe* API access

### To-Use
Copy config-sample.py to config.py and edit to suit your needs.
    python reservationist.py

Copy output to excel as a CSV and behold.

### Limitations
Lots. I hacked this in a couple of hours to do what I needed at the moment. Off of the top of my head:
* Only outputs to the screen in an ugly csv manner
* Doesn't know or care about RDS
