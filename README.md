# AmAzIn - Amazon/Azure In
## AWS managed prefix list maker for Azure ranges
### How to use

#### Setup venv
In this directory (or anywhere else) run:
```
python3 -m venv ./venv/
source ./venv/bin/activate
```
or the Windows equivilent (use WSL2 or just install Linux already! :-))

#### Install dependencies
```
pip install -r requirements.txt
```

#### Configuration
All configuration for this script is provided with environment variables - mostly as the intention is for this script to eventually be run as a Lambda and update ranges as the JSON changes. We're not there yet though... 

##### Authentication
boto3 is used in this script so you can authenticate the script using any boto3 ways. I tend to create a profile in my AWS credentials file ```.aws/credentials``` and then set:
```
export AWS_PROFILE=account_profile_name
```
AWS SSO could also be used - simply cut and paste the ID/KEY/TOKEN from the UI after sign in

See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
##### AZURE_RANGE_NAMES (required)
That JSON from Microsoft contains a number of range blocks, each with a name - for example: `AzureDevOps` or `AzureCloud.northerneurope`:

```
...
    {
      "name": "AzureDevOps",  <--- THE NAME!
      "id": "AzureDevOps",
      "properties": {
        "changeNumber": 2,
        "region": "",
        "regionId": 0,
        "platform": "Azure",
        "systemService": "AzureDevOps",
        "addressPrefixes": [
          "20.37.158.0/23",
          "20.37.194.0/24",
...
```

Specify the CIDR blocks you need in a comma-separated list with NO spaces e.g.
```
export AZURE_RANGE_NAMES=AzureDevOps,AzureCloud.northerneurope
```
The JSON is long (2000+ blocks). There are too many to make a prefix list for all of them. Nb. that AWS accounts by default are limited to 100 MPLs per
region though I suspect this can be increased if required.

##### MAX_ENTRIES (optional)
AWS Managed Prefix Lists can contain upto 100 entries. Set this to control how many ranges to add to each prefix list. Default is 50.
```
export MAX_ENTRIES=50
```

##### DOWNLOAD_PAGE_URL (optional)
This script reads the Microsoft published list of ranges from the Microsoft Downloads site. At time of writing the URL is:
```
https://www.microsoft.com/en-gb/download/confirmation.aspx?id=56519
```
but this may change. If it does set it here. 

As an aside, annoyingly this page is not a link to the JSON, so this page is scraped to obtain the actual download link. If anyone from Microsoft is reading this, please publish the list at a known URL like https://muchkindertodevs.example/azure-ranges-latest.json or similar... :-)

#### Run the script
Finally the easy part:
```
python3 ./make_prefix_list.py
```
enter MFA if required, sit back and enjoy the lists!

#### Full example
```
export AWS_PROFILE=account_profile_name
export AZURE_RANGE_NAMES=AzureDevOps,AzureCloud.northerneurope
python3 ./make_prefix_list.py

or

export AWS_ACCESS_KEY_ID="YOUR_KEY_ID"
export AWS_SECRET_ACCESS_KEY="YOUR_KEY"
export AWS_SESSION_TOKEN="YOUR_TOKEN"
export AZURE_RANGE_NAMES=AzureDevOps,AzureCloud.northerneurope
python3 ./make_prefix_list.py
```
#### What next?
Plan is to turn this into a Lambda and get it running a schedule. This seemed easy until I realised that I couldn't just delete and recreate any prefix lists that were in use. Rather than
get bogged down in complex merge logic I then thought that I could call the `modify` API to remove all the ranges from a list and re-add. This is where I started to head - `remove_entries_from_list` function is already in the code. Following the pattern found in cool stuff like instance scheduler I think the way to go will be to store state in DynamoDb (for AzureDevOps the following PLs were created e.g.) and run the updates off of that. If that sounds good, then PRs are welcome! :-) (Or I might get to it one day... Maybe...)