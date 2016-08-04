import jinja2
import argparse
import csv
import re
import os
import base64
from bwlogin import send_to_bw as bl


TEMPLATE_DIR = 'templates'
env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))

SESSION_ID = base64.b64encode(os.urandom(16))


# parsers and functions
def parse_csv(filename):
    workinglist = []
    quote_char = '"'
    delimiter = ','
    csv_to_parse = open(filename, 'r')
    csv_reader = csv.DictReader(csv_to_parse, fieldnames=[],
                                restkey='undefined-fieldnames',
                                delimiter=delimiter,
                                quotechar=quote_char)
    current_row = 0
    for row in csv_reader:
        current_row += 1
        if current_row == 1:
            csv_reader.fieldnames = row['undefined-fieldnames']
            continue
        workinglist.append(row)
    return workinglist


def add_numbers(workinglist, svcPro, SESSION_ID):
    num_add = env.get_template('addNumbers.xml').render(
        workinglist=workinglist, svcPro=svcPro, sessionId=SESSION_ID)
    return num_add


# quick and dirty parser for errors, can & should be expanded
def parse_response(orderResp):
    bwError = re.compile(
        'c:ErrorResponse" xmlns:c="C" xmlns=""\>\<summary\>(\[Warning \d{4}\] \w.*?)\</summary\>')
    errCheck = re.findall(bwError, orderResp)
    if errCheck:
        print(errCheck)
    else:
        print('Action Completed Succesfully')


# Command Line Construction
parser = argparse.ArgumentParser()
parser.add_argument('-f', '--filename', required=True)
parser.add_argument('-sp', '--svcPro', required=True)
args = parser.parse_args()
csvfile = args.filename
svcPro = args.svcPro

parsedList = parse_csv(csvfile)
numTemplate = add_numbers(parsedList, svcPro, SESSION_ID)
numberAdd = bl(numTemplate, SESSION_ID)
parse_response(numberAdd.decode())
# print(numberAdd.decode())


