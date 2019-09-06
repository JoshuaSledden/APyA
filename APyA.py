''' Name: APyA (Amazon Python Alerter).
    Description: A simple application. Used to track prices of products via web scraping a list of specified URLs.
                 The application will then e-mail the user if a price has dropped on a scraped and stored product.
    Author: Joshua Sledden - 2019
    E-mail: JoshuaSledden@Gmail.com
    Github: https://github.com/JoshuaSledden '''

# Import dependencies.
from bs4 import BeautifulSoup
import requests
import re
import threading
import time
import json
import keyboard
import smtplib

# E-mail settings.
mail_smtp = ''    # Mail server -- i.e. 'smtp.gmail.com'
mail_user = ''  # Username -- i.e. 'JoshuaSledden@Gmail.com'
mail_pass = ''  # password -- If using Gmail and you have 2-factor auth enabled please refer to: https://support.google.com/accounts/answer/185833
mail_recipient = '' # Email address of recipient -- i.e. 'Recipient@Gmail.com'

# We require a user-agent in the header so amazon doesn't prevent us from accessing the information.
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36' }

# Storage of product alerts
alerts = []

# Converts a currency string to a float using a regular expression pattern to find and remove all symbols except decimals (Expecting: $£€,)
def currency_to_float(value):
    return float(re.sub(r'[^\w|.]', '', value))

# Product type class.
class Product():
    def __init__(self, url):
        self.url = url
        self.refresh()

    # Refresh the page content and update all properties.
    def refresh(self):
        self.request_page_content()
        self.update_price()

    # Refresh the page.
    def request_page_content(self):
        page = requests.get(self.url, headers=headers)
        self.page_content = BeautifulSoup(page.content, 'html.parser')

    # Locate the scraped string for the price and update the product with it.
    def update_price(self):
        # Assign either the price via id or anything with the price class as an alternative incase the prior fails.
        new_price = self.page_content.find(id='priceblock_ourprice')
        self.price = new_price.string if not new_price == None else self.page_content.find(class_='a-color-price').string 
        
# Alert type class.
class Alert():
    def __init__(self, url, interval_seconds = 1500, last_known_price = 0.0):    
        self.create_product(url)
        self.interval_seconds = interval_seconds
        self.last_known_price = last_known_price
        self.create_worker()

    def __del__(self):
        self.stop_worker()

    # Create a product and assign it to self.
    def create_product(self, url):
        self.product = Product(url)

    # Create a worker thread that runs in the background and checks periodically for price updates.
    def create_worker(self):
        self.worker = threading.Thread(target=self.process)
        self.worker.daemon = True
        self.start_worker()

    # Start the thread worker.
    def start_worker(self):
        self.worker.start()

    # Stop the thread worker.
    def stop_worker(self):
        self.worker.join()

    # The action(s) that will occur for this alert when it discovers a price drop.
    def alert_action(self, original_price):
        print(f'Price Change on \'{self.product.url}\'. Was: {original_price} Now: {self.product.price}')
        
        # Setup the mail server to send a mail alert.
        server = smtplib.SMTP(mail_smtp, 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        
        # Login to SMTP Server.
        server.login(mail_user, mail_pass)
        
        # Construct the email.
        mail_subject = 'APyA Price Alert!'
        mail_body = f'The price of a product you have been tracking has dropped from {original_price} to {self.product.price} \nClick the link for more: {self.product.url}'     
        mail_message = f'Subject: {mail_subject}\n\n{mail_body}'
        
        # Send the email.
        server.sendmail(mail_user, mail_recipient, mail_message.encode('utf-8'))

    def check_price(self):
        # Save the original price for comparison.
        self.last_known_price = self.product.price

        # Refresh the page content.
        self.product.refresh()

        # If the refreshed product price is now less than the original, we will call the alert action.
        if currency_to_float(self.product.price) < currency_to_float(self.last_known_price):
            return True

    # Determine whether or not an alert action is necessary at this time and call it if it is.
    def process(self):
        while True:
            # If there is no product let's not waste our time.
            if self.product == None:
                return

            # Save the original price for comparison.
            self.last_known_price = self.product.price

            # Refresh the page content.
            self.product.refresh()

            # If the refreshed product price is now less than the original, we will call the alert action.
            if self.check_price():
                self.alert_action(self.last_known_price)

            time.sleep(self.interval_seconds)
            
# Load stored content and populate the alerts list with any found content.             
def load_json_content():
    print('Loading Content.json...')
    
    # Empty any current alert storage
    alerts.clear()
    
    try: # Attempt to read the content.json file or throw an error.
        with open('content.json', 'r') as read_file:
            data = json.load(read_file)
            for d in data:  # Store the data in the alerts list.
                alerts.append(Alert(d['url'], d['interval_seconds'], d['last_known_price']))
    except:
        print('Content.json read error.')
    else:
        if len(alerts) == 0:
            print('No products loaded from content.json')            
        else:
            print(f'{len(alerts)} Amazon product{"" if len(alerts) == 1 else "s"} loaded.')

# Save any updates to your content storage.
def save_json_content(): 
    print('Saving Content.json...')
    save = []
    for i in alerts:
        save.append({'url': i.product.url, 'interval_seconds': i.interval_seconds, 'last_known_price': currency_to_float(i.product.price)})
        
    with open('content.json', 'w') as outfile:
        json.dump(save, outfile, indent=4)
    print('Content.json saved.')

# Begin main application.
load_json_content()

# Welcome messages.
print('APyA (Amazon Python Alerter).')
print('Press CTRL to input commands.')

# Command functions.
def command_add_alert():
    url = input('Please enter the url of the Amazon Product: ')
    # TODO - Confirm it is a valid url.
    alerts.append(Alert(url))
    print(f'[Product Key:{len(alerts)}] New product successfully added.')

def command_delete_alert():
    command_list_alerts()
    key = int(input('Please input the worker ID of the alert you wish to delete: '))
    if key >= 0 and key < len(alerts):
        del alerts[key]
    else:
        print(f'{key} is an invalid key. Range: 0~{len(alerts)}')

def command_list_alerts():
    for _key, _alert in enumerate(alerts):
        print(f'ID:{_key} - Price:{_alert.last_known_price} - Url:{_alert.product.url}')

def command_load_alerts():
    load_json_content() # load the alert content.  

def command_save_alerts():
    save_json_content() # Save the alert content.

def command_check_prices():
    print('Performing a price check on all products...')
    [i.check_price() for i in alerts]

def command_quit():
    print('Thanks for using APyA.')
    print('Author: Joshua Sledden.')
    print('Contact: JoshuaSledden@Gmail.com')
    print('Github: https://github.com/JoshuaSledden')
    time.sleep(2)
    quit

# Provide key names to command functions to make them callable via name.
command_list = {
    'add': command_add_alert,
    'delete': command_delete_alert,
    'list': command_list_alerts,
    'load': command_load_alerts,
    'save': command_save_alerts,
    'check': command_check_prices,
    'quit': command_quit
}

# The main application loop.
while True:
    # Activate the command mode when CTRL is pressed.
    if keyboard.is_pressed('ctrl'):    
        # List all the available commands.        
        print('List of commands:')
        [print(key) for key, value in command_list.items()]
        
        # Request a user typed command and check it for validity.
        command = input('Please type a command: ')
        if command_list.get(command) == None:
            print('Invalid Command')
            continue
        
        # Call the function via key name.
        command_list[command]()