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

def parse_response(orderResp):
    bwError = re.compile(
        'c:ErrorResponse" xmlns:c="C" xmlns=""\>\<summary\>(\[Warning \d{4}\] \w.*?)\</summary\>')
    errCheck = re.findall(bwError, orderResp)
    if errCheck:
        print(errCheck)
    else:
        print('Action Completed Succesfully')

'''
# Via TCP Sockets Broadsoft only allows 15 commands per session
# before requiring logout.
'''
def delete_users(workinglist, SESSION_ID):
    for u in range(0, len(workinglist), 14):
        user_chunk = workinglist[u:u + 14]
        deletes = env.get_template('deleteUsers.xml').render(
            workinglist=user_chunk, sessionId=SESSION_ID)
        bl(deletes, SESSION_ID)




# Command Line Construction
'''
# Example command
# python deleteUsers.py -f 'deleteFile.csv'
'''
parser = argparse.ArgumentParser()
parser.add_argument('-f', '--filename', required=True)
# parser.add_argument('-sp', '--svcPro', required=True)
args = parser.parse_args()
csvfile = args.filename


parsedList = parse_csv(csvfile)

# Generate Template
deleteUserTemplate = delete_users(parsedList, SESSION_ID)

# Parse for errors
parse_response(deleteUserTemplate.decode())
