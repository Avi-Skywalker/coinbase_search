import json
from urllib.parse import urljoin
from collections import deque
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver.chrome.service import Service   
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

option = Options()
option.add_experimental_option('detach', True)
# option.add_argument('headless')

DRIVER_V = '114.0.5735.90'
BASE_LINK = 'https://www.blockchain.com/btc/tx/'
LAST_TXID = '79ec6ef52c0a2468787a5f671f666cf122f68aaed11a28b15b5da55c851aee75'


logging.basicConfig(
    level="INFO",
    format="%(asctime)s - [%(levelname)s] -> %(message)s",
    handlers=[logging.StreamHandler()]
)

def init_webdriver():

    logging.info(f'Installin chrome driver, v{DRIVER_V}')

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager(
        version=DRIVER_V).install()),
        options=option
        )

    driver.get(BASE_LINK)
    driver.maximize_window()
    driver.implicitly_wait(20)

    return driver


def bfs(driver):
    """
    This function use the Breadth first search algorithm to search for the shortest path 
    to the coinbase.
    """    
    logging.info('Running the BFS flow to find the shortest path to coinbase')
    
    queue_to_explore = deque([(LAST_TXID, [])])
    input_txids_explored = set()

    while queue_to_explore:
        curr_txid, leading_txids = queue_to_explore.popleft()
        logging.debug(f'Current txid: {curr_txid}')
        input_txids_explored.add(curr_txid)

        contains_coinbase, coinbase_txid, all_descendant_txids =\
            check_if_current_txid_contains_coinbase(driver, curr_txid)
        if contains_coinbase:
            leading_txids.append(curr_txid)
            filtered_txid_list = set(leading_txids)
            return filtered_txid_list, coinbase_txid
        
        descendant_txids, initial_link = validate_input_transactions(driver, all_descendant_txids)
        
        for descendant in descendant_txids:
            if descendant['txid'] not in input_txids_explored:
                leading_txids.append(curr_txid)
                queue_to_explore.append((descendant['txid'], leading_txids))
        driver.get(initial_link)
        driver.implicitly_wait(10)


def check_if_current_txid_contains_coinbase(driver, curr_txid):
    """
    Loads the json content and checks whenever one of the input is the coinbase
    """
    logging.info('Check if current txid has the coinbase transaction as one of the inputs')
    driver.implicitly_wait(5)
    redirect_by_link(driver, urljoin(BASE_LINK, curr_txid))
    json_content = load_json_content(driver)
    if json_content:
        for input in json_content:
            if input['coinbase']:
                logging.info('Reached coinbase txid!')
                return True, input['txid'], json_content
    
    logging.info('No coinbase inputs, continue...')
    return False, None, json_content


def validate_input_transactions(driver, all_descendant_txids):
    """
    Validates all the inputs to ensure the driver will be able to check their content
    """
    logging.info('Validating input transactions')
    initial_link = driver.current_url
    valid_descendants = []
    for descendant in all_descendant_txids:
        logging.info(f'Checking {descendant["txid"]}')
        redirect_by_link(driver, urljoin(BASE_LINK, descendant['txid']))
        logging.info('Moved to descendant link')
        if load_json_content(driver):
            valid_descendants.append(descendant)

    return valid_descendants, initial_link

def load_json_content(driver):
    """
    Searches for the json button, loads & return the json content
    """
    logging.info(f'Loading json content at: {driver.current_url}')
    driver.implicitly_wait(5)
    attempts = 0
    while attempts < 30:
        try:
            json_button = driver.find_elements(By.XPATH, '//button[text()="JSON"]')[0]
            json_button.click()
            logging.info('Located json button')
            break
        except StaleElementReferenceException or IndexError:
            driver.refresh()
            attempts += 1
            logging.warning('Json element not found, waiting...')

    json_element = driver.find_elements(By.XPATH, '//pre[@class="sc-6abc7442-1 eIwaHT"]')[0]
    logging.info(f'Found json content')
    driver.implicitly_wait(10)
    parsed_data = None
    attempts = 0
    while not parsed_data and attempts < 30:
        try:
            parsed_data = json.loads(json_element.text)['inputs']
        except json.JSONDecodeError:
            attempts +=1
            logging.warning('Retrying to load json content')

    return parsed_data


def check_target_page(driver, current_link):
    """
    Checks if input page contains coinbase in the list
    """
    links_on_current_page = []
    link_to_coinbase = None
    try:
        driver.get(urljoin(BASE_LINK, current_link))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")

        driver.implicitly_wait(10)
        json_contet = load_json_content(driver)

        for input in json_contet:
            if input['coinbase']:
                link_to_coinbase = input['txid']
                break
            links_on_current_page.append(input['txid'])
    except WebDriverException:
        logging.warning('Empty page')

    return link_to_coinbase, links_on_current_page


def redirect_by_link(driver, link, timout=5, attempts=30):
    """
    Wrapper function for link redirection
    """
    attempt = 0
    driver.get(link)
    logging.info(f'Redirecting to: {link}')
    
    while not links_equal(driver, link) and attempt < attempts:
        driver.get(link)
        driver.implicitly_wait(timout)
        attempt += 1

        print(f'Not redirected yet, waiting')

def links_equal(driver, target_link):
    """
    Used to check if current link is the desired target
    """
    return driver.current_url.split('/')[-1] == target_link.split('/')[-1]


if __name__ == "__main__":
    driver = init_webdriver()
    shortest_chain, coinbase_txid = bfs(driver)
    print('Found shortest transactions chain to coinbase:')
    [print(i,'--->',txid) for (i, txid) in enumerate(shortest_chain, start=1)]