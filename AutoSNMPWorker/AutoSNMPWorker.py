
#------------line_notify.py and Worker------------
#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import requests
import json
from requests.exceptions import HTTPError
from pysnmp.hlapi import *
import smtplib , ssl
from dateutil.parser import parse
from dateutil import tz
import datetime
import pytz
import email

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Variable Information 
WEBAPI_URL = 'https://localhost:44355/api/Interfaces'
TIMEZONE = "Etc/GMT+7"

class snmpSetting:
    oid_int_status = "1.3.6.1.2.1.2.2.1.8"
    community = "thix-iig"

class emailSetting:
    senderEmail =  "nonhahere.4822@gmail.com"
    senderEmailPassword = "narawit4822!"
    emailServer = "smtp.gmail.com"
    emailServerPort = 465

class lineSetting:
    Line_url = 'https://notify-api.line.me/api/notify'

#SNMP Function
def snmp_get(oid, hostip):
    errorIndication, errorStatus, errorIndex, varBinds = next(
        getCmd(SnmpEngine(),
               CommunityData(snmpSetting.community, mpModel=0),
               UdpTransportTarget((hostip, 161)),
               ContextData(),
               ObjectType(ObjectIdentity(oid)))
    )

    if errorIndication:
        print(errorIndication)
    elif errorStatus:
        print('%s at %s' % (errorStatus.prettyPrint(),
                            errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))

    #get OID
    return int(varBinds[0][1]) #get value


#Access Database via WebAPI 
def GetInterfaceList(usrlink):
    try:
        response = requests.get(usrlink , verify = False) #solve by verify --> False
        interface_list = response.json()
        return interface_list
    # If the response was successful, no Exception will be raised
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')  # Python 3.6
    except Exception as err:
        print(f'Other error occurred: {err}')  # Python 3.6

#Update Interface Database via WebAPI
def UpdateInterface(usrlink , item):
    headers={'Content-type':'application/json', 'Accept':'application/json'}

    useURL = usrlink + "/" + item['id']
    passingData = json.dumps(item)

    try:
        response = requests.put(useURL , data = passingData , verify = False , headers=headers) #solve by verify --> False
    # If the response was successful, no Exception will be raised
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')  # Python 3.6
    except Exception as err:
        print(f'Other error occurred: {err}')  # Python 3.6
    return response


##line notifucation
def LineNotification(msg, token):
    if(token == None):
        return 

    Line_headers = {'content-type':'application/x-www-form-urlencoded','Authorization':'Bearer '+token}

    try:
        response = requests.post(lineSetting.Line_url ,headers=Line_headers ,data = {'message':msg}) #solve by verify --> False
        return response
    # If the response was successful, no Exception will be raised
    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')  # Python 3.6
    except Exception as err:
        print(f'Other error occurred: {err}')  # Python 3.6
    

## Email Sending
def EmailNotification(header , body , receiver_emails):
    if(receiver_emails == None):
        return 
    context = ssl.create_default_context()

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = emailSetting.senderEmail
    message["Subject"] = header
    message["To"] = receiver_emails

    message.attach(MIMEText(body,"plain"))

    # Get Receiver email
    receiver_emails = receiver_emails.split(",")
    print(receiver_emails)

    for receiver_email in receiver_emails:
        text = message.as_string()
        with smtplib.SMTP_SSL(emailSetting.emailServer,emailSetting.emailServerPort , context=context) as server:
            server.login(emailSetting.senderEmail,emailSetting.senderEmailPassword)
            server.sendmail(emailSetting.senderEmail , receiver_email , text)



def GetDateTimeType(strTime):
    # Create datetime object
    d = parse(strTime)
    #d = datetime.datetime.strptime(strTime, "%Y-%m-%dT%H:%M:%S.%f")
    return d

def GetLocalTimeZone(d):

    # Auto-detect zones:
    from_zone = tz.tzutc()
    to_zone = pytz.timezone(TIMEZONE)

    # Tell the datetime object that it's in UTC time zone since 
    # datetime objects are 'naive' by default
    d = d.replace(tzinfo=to_zone)

    # Convert time zone
    central = d.astimezone(to_zone)
    nownew = GetNowLocalTimeZone()

    # Get the Result
    return central

def GetNowLocalTimeZone():
    d = datetime.datetime.now()
    timezone = pytz.timezone(TIMEZONE)
    d_aware = timezone.localize(d)
    return d_aware

################################################### Main ###################################################

# Get - Interface - List 
Interface_list = GetInterfaceList(WEBAPI_URL);

# Discover And Notify when Status has changes.
for item in Interface_list:

    # Confiqure Variable used in operation
    muteDateUntill = GetLocalTimeZone(GetDateTimeType(item['muteUntill']))
    eventFlapStartTime = GetLocalTimeZone(GetDateTimeType(item['eventFlapStartTime']))
    nowDate = GetNowLocalTimeZone();
    #diffTest = (eventFlapStartTime - GetNowLocalTimeZone() ).total_seconds()

    # SNMP Query
    interfaceIndex = snmpSetting.oid_int_status + "." + item['index']
    newItemStatus = snmp_get(interfaceIndex, item['hostIP'])

    # Compare Old Interface Status in db and New-Status
    if(newItemStatus != item['lastStatus']):

        ### provide notification message for sending to line, email
        lastStatusString = "Down" if item['lastStatus']==2 else "Up" 
        newItemStatusString = "Down" if newItemStatus ==2 else "Up"


        
        headerMessage = "NOAH " + item['hostName'] + " " + item['name'] + " Status " +lastStatusString + " -> " + newItemStatusString
        
        emailBodyMessage = "\nEquipment:\t\t" + item['hostName'] + "\nIP Address:\t\t" + item['hostIP'] + "\nInterface:\t\t" + item['name'] + "\nCurrent Status:\t" + newItemStatusString + "\nTime:\t\t\t" + str(datetime.datetime.now())
        lineBodyMessage = "\n" + item['hostName'] + "\nInterface: " + item['name'] + "\nStatus: " + lastStatusString + " -> " + newItemStatusString

        ### update new status but not to DB
        item['lastStatus'] = newItemStatus

        if(item['email'] != None or item['lineGroup'] != None):
            if(not item['pause']): # not pause
                if(item['muteEnable']):
                    #Check it still mute ?
                    timeSpan = ( muteDateUntill - nowDate).total_seconds()
                    if(timeSpan > 0): # not muted, Go
                        # Update new Status without notify
                        t = UpdateInterface(WEBAPI_URL , item )
                        print('Interface has changes but it\'s not notify ( Muted )')
                        continue
                if(item['eventEnable']):
                    dateTimeFlapBound = parse(item['eventFlapStartTime']) + datetime.timedelta(minutes=item['eventTriggerInterval'])
                    dateTimeFlapBound = GetLocalTimeZone(dateTimeFlapBound)
                            
                    if( (dateTimeFlapBound - nowDate).total_seconds() < 0):# so long occur 
                        print('It\'s has been occur so far, for the last EventFlapStartTime: ' + item['eventFlapStartTime'])
                        item['eventFlapStartTime'] = nowDate.strftime("%Y-%m-%dT%H:%M:%S")
                        print('then I will set new EventFlapStartTime to ' + item['eventFlapStartTime'])
                        item['eventFlapCount'] = 1
                    else:  # occur in flap range
                        print('It\'s still can Flapping untill ' + str(dateTimeFlapBound))
                        item['eventFlapCount'] = item['eventFlapCount'] + 1
                    if( item['eventFlapCount'] < item['eventFlapMax']):
                        print("Count: "+str(item['eventFlapCount']))
                        #send notification
                        LineNotification(lineBodyMessage, item['lineToken'])
                        EmailNotification(headerMessage , emailBodyMessage , item['email'])
                    else:
                        print("Flapping Count is over the maximum, Max: " + str(item['eventFlapMax']) + " Count: " + str(item['eventFlapCount']))
                        # Update new Status without notify
                        t = UpdateInterface(WEBAPI_URL , item )
                        continue
                else:
                    print('Event Trigger isn\'t enable')
                    #send notification 
                    LineNotification(lineBodyMessage, item['lineToken'])
                    EmailNotification(headerMessage , emailBodyMessage ,item['email'])
    t = UpdateInterface(WEBAPI_URL , item )

