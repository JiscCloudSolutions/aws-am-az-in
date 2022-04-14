import json
import os

from bs4 import BeautifulSoup
import requests
import boto3
from botocore.config import Config

import logging

logging.basicConfig(level=logging.INFO)

AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
DOWNLOAD_PAGE_URL = os.getenv("AZURE_RANGE_URL", "https://www.microsoft.com/en-gb/download/confirmation.aspx?id=56519")
MAX_ENTRIES = int(os.getenv("AWS_MAX_ENTRIES_PER_LIST", 50))
AZURE_RANGE_NAMES = os.getenv("AZURE_RANGE_NAMES", "AzureDevOps,AzureCloud.northeurope")

boto3_config = Config(
    region_name = "eu-west-1"
)

ec2_client = boto3.client("ec2", config=boto3_config)

def parse_range_names():
    return AZURE_RANGE_NAMES.split(',')

def create_prefix_list(prefix_list_name, entries, address_family):
    try:
        create_response = ec2_client.create_managed_prefix_list(
            DryRun = False,
            PrefixListName = prefix_list_name,
            Entries = entries,
            MaxEntries = len(entries),
            TagSpecifications=[
                {
                    'ResourceType': 'prefix-list',
                    'Tags': [ { 'Key': 'CreatedBy', 'Value': 'AwsAzurePrefixListMaker' }]
                }
            ],
            AddressFamily = address_family
        )
    except Exception as e:
        logging.error("Trouble creating prefix list %s:\n====\n%s\n====\n" %(prefix_list_name, e))

def only_cidr(entry):
    return entry["Cidr"]

def remove_entries_from_list(prefix_list_name):
    try: 
        lookup_res = ec2_client.describe_managed_prefix_lists(
            Filters = [ { "Name": "prefix-list-name", "Values": [ prefix_list_name ]}]
        )
        for prefix_list in lookup_res["PrefixLists"]:
            logging.debug("Clearing entries from %s" %(prefix_list["PrefixListId"]))
            entries_result = ec2_client.get_managed_prefix_list_entries(
                PrefixListId = prefix_list["PrefixListId"],
                MaxResults = MAX_ENTRIES
            )
            entries_to_clear = map(only_cidr, entries_result["Entries"])
            clear_result = ec2_client.modify_managed_prefix_list(
                PrefixListId = prefix_list["PrefixListId"],
                RemoveEntries = entries_to_clear
            )
    except Exception as e:
        logging.error("Trouble clearing prefix list %s:\n====\n%s\n====\n" %(prefix_list_name, e))

def remove_prefix_list(prefix_list_name):
    try: 
        lookup_res = ec2_client.describe_managed_prefix_lists(
            Filters = [ { "Name": "prefix-list-name", "Values": [ prefix_list_name ]}]
        )
        for prefix_list in lookup_res["PrefixLists"]:
            logging.debug("Removing list named %s" %(prefix_list["PrefixListId"]))
            ec2_client.delete_managed_prefix_list(
                PrefixListId = prefix_list["PrefixListId"]
            )
    except Exception as e:
        logging.error("Trouble removing prefix list %s:\n====\n%s\n====\n" %(prefix_list_name, e))        

def tidy_name(name):
    return name.lower().replace(".", "-")

def create_ipv4_entries(prefixes):
    entries = []
    for prefix in prefixes:
        if ('.' in prefix):
            entries.append({
                "Cidr": prefix,
                "Description": prefix
            })
    return [entries[i:i+MAX_ENTRIES] for i in range(0, len(entries), MAX_ENTRIES)]

def create_ipv6_entries(prefixes):
    entries = []
    for prefix in prefixes:
        if (':' in prefix):
            entries.append({
                "Cidr": prefix,
                "Description": prefix
            })
    return [entries[i:i+MAX_ENTRIES] for i in range(0, len(entries), MAX_ENTRIES)]    

def read_azure_range_json(range_names_filter):
    try: 
        download_page = requests.get(DOWNLOAD_PAGE_URL)
        pagesoup = BeautifulSoup(download_page.content, features="html.parser")

        for spanner in pagesoup.find_all("span", class_="file-link-view1"):
            json_url = spanner.a['href']

        full_json = json.loads(requests.get(json_url).text)

        range_blocks = []

        for range_block in full_json['values']:
            if range_block['name'] in range_names_filter:
                range_blocks.append(range_block)

        return range_blocks
    except Exception as e:
        logging.error("Trouble reading azure ranges from %s:\n====\n%s\n====\n" %(DOWNLOAD_PAGE_URL, e))

def handler(event, context):
    range_names = parse_range_names()

    range_blocks = read_azure_range_json(range_names)

    created_result = []

    for block in range_blocks:
        list_name = tidy_name(block['name'])

        ipv4_entries = create_ipv4_entries(block['properties']['addressPrefixes'])
        ipv6_entries = create_ipv6_entries(block['properties']['addressPrefixes'])

        print(ipv4_entries)

        i = 1
        for ipv4_entries_chunk in ipv4_entries:  
            ipv4_list_name = "azure-%s-pl-ipv4-%s" %(list_name, i)
            logging.info("Creating prefix list %s" %(ipv4_list_name))
            remove_prefix_list(ipv4_list_name)
            create_prefix_list(ipv4_list_name, ipv4_entries_chunk, "IPv4")
            created_result.append(ipv4_list_name)
            i = i + 1

        i = 1
        for ipv6_entries_chunk in ipv6_entries:
            ipv6_list_name = "azure-%s-pl-ipv6-%s" %(list_name, i)
            logging.info("Creating prefix list %s" %(ipv6_list_name))
            remove_prefix_list(ipv6_list_name)
            create_prefix_list(ipv6_list_name, ipv6_entries_chunk, "IPv6")
            created_result.append(ipv6_list_name)
            i = i + 1

    response = {
        "statusCode": 200,
        "body": json.dumps({'created':created_result})
    }

    logging.debug("Finished, with response:\n====\n%s\n====\n" %(response))

    return response

if __name__ == "__main__":
  print("Creating lists...")
  print(handler({},{}))
