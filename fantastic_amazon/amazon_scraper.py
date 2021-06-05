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



def change_proxy(proxy_info, ua):
    "Define Firefox Profile with you ProxyHost and ProxyPort"
    profile = webdriver.FirefoxProfile()
    fireFoxOptions = webdriver.FirefoxOptions()
    # fireFoxOptions.set_headless()
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

    def requester(self, url, page_num, try_count=0, ):
        self.browser = change_proxy(random.choice(self.proxies), ua.random) if not self.browser else self.browser
        while True:
            self.browser.get(url) if page_num <= 1 else self.browser.find_element_by_css_selector('.a-last > a:nth-child(1)').click()
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
        return "https://www." + amazon_site + "/dp/product-reviews/" + product_asin + f"?pageNumber={page_number}"

    def scrape(self, amazon_site, url=None, asin=None):
        reviews = {"date_info": [], "name": [],
                   "title": [], "content": [], "rating": []}
        asin = self.find_asin(url) if url else asin
        page_1 = self.requester(self.generate_url(amazon_site, asin, 1), page_num=1)
        total_pages = self._get_total_pages(page_1)
        for page in range(total_pages):
            response = page_1 if page < 1 else self.requester(self.generate_url(amazon_site, asin, page + 1), page_num=page)
            self._page_scraper(response=response, reviews_dict=reviews)
        self.close_browser()
        return reviews

    def close_browser(self, ):
        try:
            self.browser.close()
        except Exception as e:
            pass
        self.browser = None

    def _page_scraper(self, response: requests.Response, reviews_dict: dict):

        reviews = BeautifulSoup(response, 'html.parser').findAll(
            "div", {"class": "a-section review aok-relative"})
        reviews = BeautifulSoup(
            '<br/>'.join([str(tag) for tag in reviews]), 'html.parser')

        titles = _helper(reviews, ["a", "span"], "class", "review-title", sort_func=lambda x: x.find('span').text)
        names = _helper(reviews, "span", "class", "a-profile-name", sort_func=lambda x: x.text)
        ratings = _helper(reviews, ["i", ], "data-hook", ["review-star-rating", "cmps-review-star-rating"], sort_func=lambda x: float(x.text.split(' out')[0]))
        date_list = _helper(reviews, "span", "data-hook", "review-date", sort_func=lambda x: x.text.split('on ')[-1])
        contents = _helper(reviews, "span", "data-hook", "review-body", sort_func=lambda x: x.text.strip())

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

    AmazonScrapper().scrape("amazon.com", url="https://www.amazon.com/StarTech-com-2-Port-USB-C-HDMI-MST/dp/B06XPVGQKY/ref=sr_1_6?dchild=1&keywords=USB-C+to+Dual+hdmi+Video+Adapter&qid=1621983776&sr=8-6")
    