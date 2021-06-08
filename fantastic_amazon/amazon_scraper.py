import selenium.common.exceptions
from selenium import webdriver
from fake_useragent import UserAgent
import requests
from bs4 import BeautifulSoup
import time
import random
import math
import re
from requests.models import Response

# to ignore SSL certificate errors
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# random user-agent
ua = UserAgent(verify_ssl=False)


# browser = webdriver.Firefox()


def proxy_generator():
    proxies = []
    response = requests.get("https://sslproxies.org/")
    soup = BeautifulSoup(response.content, 'html.parser')
    proxies_table = soup.find(id='proxylisttable')
    for row in proxies_table.tbody.find_all('tr'):
        proxies.append({
            'ip':   row.find_all('td')[0].string,
            'port': int(row.find_all('td')[1].string)
        })

    # proxies_lst = [{'http': 'http://'+proxy['ip']+':'+proxy['port']}
    #                for proxy in proxies]
    return proxies


def change_proxy(proxy_info, ua, headless=False):
    "Define Firefox Profile with you ProxyHost and ProxyPort"
    profile = webdriver.FirefoxProfile()
    fireFoxOptions = webdriver.FirefoxOptions()
    if headless:
        fireFoxOptions.set_headless()
    profile.set_preference("network.proxy.type", 1)
    profile.set_preference("network.proxy.http", proxy_info['ip'])
    profile.set_preference("network.proxy.http_port", int(proxy_info['port']))
    profile.set_preference("general.useragent.override", ua)
    profile.update_preferences()
    return webdriver.Firefox(firefox_profile=profile, options=fireFoxOptions)


def _helper(content, tag, parameter_key, parameter_value, sort_func):
    return [sort_func(attribute) for attribute in content.find_all(tag, {parameter_key: parameter_value})]


class AmazonScrapper:

    def __init__(self) -> None:

        self.proxies = proxy_generator()
        self.browser = None
        self.headless = False

    def _get_search_results(self, url, search_terms):
        self.browser = change_proxy(random.choice(
            self.proxies), ua.random, self.headless)
        self.browser.get(url)
        search_bar = self.browser.find_element_by_id('twotabsearchtextbox')
        search_bar.send_keys(search_terms)
        search_bar.click()
        # search_bar.send_keys(' ')
        time.sleep(random.uniform(1, 2))
        try:
            suggestions = self.browser.find_element_by_id('suggestions').text.split('\n')
        except Exception as e:
            suggestions = []
        self.browser.find_element_by_id('nav-search-submit-button').click()
        return self.browser.page_source, suggestions

    def requester(self, url, page_num, try_count=0, ):
        self.browser = change_proxy(random.choice(
            self.proxies), ua.random, self.headless) if not self.browser else self.browser
        while True:
            if page_num <= 1:
                self.browser.get(url)
            else:
                refresh_count = 0
                while True:
                    try:
                        self.browser.find_element_by_css_selector(
                            '.a-last > a:nth-child(1)').click()
                        break
                    except selenium.common.exceptions.NoSuchElementException:
                        self.browser.refresh()
                        refresh_count += 1
                        if refresh_count > 5:
                            self.browser.get(url)
            response = self.browser.page_source
            if "api-services-support@amazon.com" in response:
                if try_count > 5:
                    raise Exception("CAPTCHA is not bypassed")
                self.close_browser()
                self.requester(url, page_num=page_num, try_count=try_count+1)
            else:
                break

        time.sleep(random.uniform(3, 10))

        return response

    def generate_url(self, amazon_site, product_asin, page_number):
        return "".join(["https://www.", amazon_site, "/dp/product-reviews/", product_asin, f"?pageNumber={page_number}"])

    def generate_product_url(self, amazon_site, product_asin,):
        return "".join(["https://www.", amazon_site, "/dp/", product_asin])

    def scrape(self, amazon_site, url=None, asin=None, headless=False):
        count = 0
        self.headless = headless
        while True:
            try:
                reviews = {"date_info": [], "name": [],
                           "title": [], "content": [], "rating": []}
                asin = self.find_asin(url) if url else asin
                url_1 = self.generate_url(amazon_site, asin, 1)
                print(f"scraping: {url_1}")
                page_1 = self.requester(url_1, page_num=1)
                total_pages = self._get_total_pages(page_1)
                for page in range(total_pages):
                    url = self.generate_url(amazon_site, asin, page + 1)
                    response = page_1 if page < 1 else self.requester(
                        url, page_num=page)
                    try:
                        self._page_scraper(
                            response=response, reviews_dict=reviews)
                    except Exception as e:
                        print(e, url)
                        pass
                self.close_browser()
                return reviews
            except Exception as e:
                print(e)
                count += 1
                if count > 5:
                    raise Exception("Pulling Reviews Failed")

    def scrape_search(self, amazon_site, search_terms, headless=False):
        count = 0
        self.headless = headless
        while True:
            try:
                response, search_suggestions = self._get_search_results(
                    url="".join(["https://www.", amazon_site]), search_terms=search_terms)
                results = self._search_page_scraper(response)
                results['suggestions'] = search_suggestions
                self.close_browser()
                return results
            except Exception as e:
                print(f"Errored out on {search_terms}", e)
                count += 1
                if count > 5:
                    self.close_browser()
                    raise Exception("Pulling Reviews Failed")

    def scrape_product_page(self, amazon_site, url=None, asin=None, headless=False):
        self.headless = headless
        count = 0
        while True:
            try:
                asin = self.find_asin(url) if url else asin
                url_1 = self.generate_product_url(amazon_site, asin)
                page_1 = self.requester(url_1, page_num=1)
                self.close_browser()
                return self._product_page_scraper(page_1, )
            except Exception as e:
                print(f"Errored out on {url_1}", e)
                count += 1
                if count > 5:
                    self.close_browser()
                    raise Exception("Pulling Reviews Failed")

    def close_browser(self, ):
        try:
            self.browser.close()
        except Exception as e:
            pass
        self.browser = None

    def _search_page_scraper(self, response: requests.Response):
        search_page = BeautifulSoup(response, 'html.parser')
        product_cards = search_page.findAll('div', {'class': 's-asin'})
        results = {}
        for product in product_cards:
            try:
                index = product.attrs['data-index']
                results[index] = {
                    'asin': product.attrs['data-asin'],
                    'ad': 'AdHolder' in product.attrs['class'],
                    'amazon_choice': "Amazon's Choice" in product.text,
                    'title': product.findAll('span', {"class": "a-size-medium a-color-base a-text-normal"})[0].text,
                    'price': float(product.findAll('span', {"class": "a-price-whole"})[0].text.strip('.').strip(',')) +  
                             float(product.findAll('span', {"class": "a-price-fraction"})[0].text) / 100,
                    "coupon": 'coupon' in product.text
                }
            except IndexError:
                pass
        return results

    def _product_page_scraper(self, response: requests.Response):
        product_page = BeautifulSoup(response, 'html.parser')
        title = product_page.select('#productTitle')[0].text.strip()
        price = None
        for _id in ['#priceblock_ourprice', '#priceblock_dealprice', '#priceblock_saleprice']:
            try:
                price = product_page.select(_id)[0].text.strip()
                break
            except IndexError:
                pass
        bullets = [span.text for span in product_page.select('#feature-bullets')[0].findAll(
            "span", {"class": "a-list-item"}) if not 'class' in span.previous.attrs]
        aplus_content = product_page.findAll(
            "div", {"id": "aplus"})[0].text.strip()
        rating = product_page.findAll(
            "span", {"data-hook": "rating-out-of-text"})[0].text.split(' out')[0]
        return {'title': title, 'price': price, 'bullets': bullets, 'aplus_content': aplus_content, 'rating': rating}

    def _page_scraper(self, response: requests.Response, reviews_dict: dict):
        reviews = BeautifulSoup(response, 'html.parser').findAll(
            "div", {"class": "a-section review aok-relative"})
        reviews = BeautifulSoup(
            '<br/>'.join([str(tag) for tag in reviews]), 'html.parser')

        titles = _helper(reviews, [
                         "a", "span"], "class", "review-title", sort_func=lambda x: x.find('span').text)
        names = _helper(reviews, "span", "class",
                        "a-profile-name", sort_func=lambda x: x.text)
        ratings = _helper(reviews, ["i", ], "data-hook", ["review-star-rating",
                          "cmps-review-star-rating"], sort_func=lambda x: float(x.text.split(' out')[0]))
        date_list = _helper(reviews, "span", "data-hook", "review-date",
                            sort_func=lambda x: x.text.split('on ')[-1])
        contents = _helper(reviews, "span", "data-hook",
                           "review-body", sort_func=lambda x: x.text.strip())

        reviews_dict['date_info'].extend(date_list)
        reviews_dict['name'].extend(names)
        reviews_dict['title'].extend(titles)
        reviews_dict['content'].extend(contents)
        reviews_dict['rating'].extend(ratings)

    @staticmethod
    def _get_total_pages(response):
        soup = BeautifulSoup(response, 'html.parser')
        content = soup.find_all(
            "div", {"data-hook": "cr-filter-info-review-rating-count"})
        total_reviews = int(content[0].find_all("span")[0].get_text(
            "\n").strip().split(" ")[4].replace(",", ""))
        print("Total reviews (all pages): {}".format(total_reviews), flush=True)
        total_pages = math.ceil(total_reviews/10)
        return total_pages

    @staticmethod
    def find_asin(url):
        split = url.split('/')
        return [_split for _split in split if len(_split) == 10 and _split.isalnum()][0]


if __name__ == "__main__":

    AmazonScrapper().scrape_search("amazon.com", search_terms="USBC to 4K DisplayPort")
