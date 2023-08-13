"""
scripts for fetching faved twitter images
"""
import io
import os
import time
import random
import json
import base64
import pathlib
from urllib.parse import urlparse

from selenium import webdriver
# from selenium.webdriver.firefox.options import Options
# from selenium.webdriver import FirefoxOptions
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver import Keys, ActionChains
from selenium.common.exceptions import NoSuchElementException, JavascriptException
from PIL import Image

# opts = FirefoxOptions()
chrome_options = ChromeOptions()
# chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--disable-extensions')
chrome_options.add_argument('--disable-infobars')
chrome_options.add_argument('enable-automation')
chrome_options.add_argument("--headless")
chrome_options.add_argument("--enable-file-cookies")
# For background screenshot
# See https://chromium.googlesource.com/chromium/src.git/+/6dee4949eb9070d8c500b4c7f23643efa00196f2
chrome_options.add_argument("--disable-backgrounding-occluded-windows")
chrome_options.add_argument("user-data-dir=selenium")


BACKUP_CODE_XPATH = "//*[text()='Use a backup code']"
LOGIN_SUCCESS_XPATH = "//*[text()='Welcome to Twitter!']"
ERROR_XPATH = "//*[text()='Error']"
INPUT_BACKUP_CODE_XPATH = "//*[text()='Enter code']"
NEXT_BUTTON_XPATH = "//*[text()='Next']"
SAVE_PATH = 'downloaded'

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BACKUP_CODE = os.getenv("BACKUP_CODE")
FRONT_PAGE = 'https://twitter.com'

FETCH_IMG_TEMPLATE = """
return new Promise((resolve, reject) => {
    const toDataURL = url => fetch(url)
      .then(response => response.blob())
      .then(blob => new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onloadend = () => resolve(reader.result)
        reader.onerror = reject
        reader.readAsDataURL(blob)
      }))

    toDataURL('%%image-url%%')  // Replace with your actual URL
      .then(dataUrl => resolve(dataUrl))
      .catch(err => reject(err));
});
"""

remote_url = 'http://127.0.0.1:9515'
# remote_url = 'http://192.168.0.4:9515'
driver = webdriver.Remote(
    remote_url,
    # keep_alive=True,
    options=chrome_options,
)
driver.set_window_size(1920, 1080)
driver.set_page_load_timeout(60)  # slow cpu
# driver.maximize_window()

def save_image_from_data_url(img_name : str, data_url : bytes, output_path : str) -> None:
    # Decode the base64 data into bytes
    img_bytes = base64.b64decode(data_url.split(b',', 1)[1])

    # Open the bytes as an image
    img = Image.open(io.BytesIO(img_bytes))

    # Save the image
    output_img = os.path.join(output_path, f'{img_name}.{img.format.lower()}')
    if pathlib.Path(output_img).is_file() is False or len(Image.open(output_img).tobytes()) < len(img.tobytes()):
        img.save(output_img)
        print(f"Image has been saved as {output_img}")
    else:
        print(f"{output_img} already exists, ignore.")


def fetch_img(img_url):
    print(f"Start fetching image {img_url}")
    return driver.execute_script(FETCH_IMG_TEMPLATE.replace("%%image-url%%", img_url))


def get_image_name(img, url):
    parsed_url = urlparse(url)
    img_id = parsed_url.path.rsplit('/', 1)[-1]

    tweet_photo_url = img.find_element(By.XPATH, '../../../..').get_attribute('href')
    if tweet_photo_url is None:
        return f'{img_id}'
    _, author, _, twitter_id, _ = urlparse(tweet_photo_url).path.split('/', 4)
    return f'{author}_{twitter_id}_{img_id}'


def download_images(max_error_cnt=3):
    imgs = driver.find_elements(By.XPATH, '//img[@alt="Image"]')
    last_img = None
    viewed_urls = set()
    for img in imgs:
        url = img.get_attribute('src')
        viewed_urls.add(url)
        # ignore side images
        if "name=240x240" in url or "name=360x360" in url:
            continue
        else:
            last_img = img
        url = url.replace("format=jpg", "format=png").replace("name=small", "name=large").replace("name=900x900", "name=large")
        print(f"downloading image url: {url}")

        image_name = get_image_name(img, url)

        if pathlib.Path(os.path.join(SAVE_PATH, f'{image_name}.png')).is_file():
            print('Image already exists, ignore.')
            continue

        error_cnt = 0
        while error_cnt < max_error_cnt:
            try:
                img_data = fetch_img(url)
                break
            except JavascriptException as err:
                error_cnt += 1
                if error_cnt == max_error_cnt:
                    raise
                print(str(err))
                time.sleep(10.0)

        save_image_from_data_url(image_name, img_data.encode('ascii'), SAVE_PATH)

    return last_img, viewed_urls


def is_login():
    raise NotImplementedError()


def scroll_download(max_error_cnt=3, max_scroll=1000):
    # TODO: optimize
    loop = 0
    previous_urls = set()
    while loop < max_scroll:
        print(f"loop: {str(loop)}")
        error_cnt = 0
        while error_cnt < max_error_cnt:
            try:
                last_img, viewed_urls = download_images()
                print(len(viewed_urls))
                if len(viewed_urls.union(previous_urls)) == len(previous_urls):
                    print('no scroll items!')
                    return
                previous_urls = viewed_urls
                break
            except Exception as err:
                error_cnt += 1
                if error_cnt == max_error_cnt:
                    raise
                print(err)
        ActionChains(driver).scroll_to_element(last_img).perform()
        time.sleep(5.0)
        loop += 1


def move_to_next():
    first_fav = driver.find_element(By.XPATH, '//img[@alt="Image"][1]')
    ActionChains(driver).scroll_to_element(first_fav).perform()
    # ActionChains(driver).click(first_fav).perform()


def twitter_login(max_error_count=3) -> bool:
    '''
    TODO: support 2-step auth login
    '''
    driver.get(FRONT_PAGE)
    error_count = 0
    while error_count < max_error_count:
        time.sleep(5.0)
        try:
            input_ = driver.find_element(By.XPATH, "//*[text()='Phone, email, or username']")
            error_count = 0
            break
        except NoSuchElementException:
            print("no login page!")
            error_count += 1
    # input username
    print('Inputting username...')
    ActionChains(driver).move_to_element(input_).click().send_keys(USERNAME).perform()
    time.sleep(1.0 + random.random())
    next_btn = driver.find_element(By.XPATH, "//*[text()='Next']")
    # click next
    ActionChains(driver).move_to_element(next_btn).click().perform()
    # OK
    # ok_btn = driver.find_element(By.XPATH, "//*[text()='OK']")
    # error_ele = driver.find_element(By.XPATH, "//*[text()='Error']")

    # input password
    print('Inputting password...')
    time.sleep(3.0 + random.random())
    password_input =  driver.find_element(By.XPATH, "//*[text()='Password']")
    ActionChains(driver).move_to_element(password_input).click().send_keys(PASSWORD).perform()
    login_btn = driver.find_element(By.XPATH, "//*[text()='Log in']")
    ActionChains(driver).move_to_element(login_btn).click().perform()

    # wait a while
    while True:
        time.sleep(15.0)
        try:
            driver.find_element(By.XPATH, LOGIN_SUCCESS_XPATH)
            print("log in successful!")
            break
        except NoSuchElementException:
            pass
        try:
            driver.find_element(By.XPATH, BACKUP_CODE_XPATH)
            print("need backup code!")
            break
        except NoSuchElementException:
            pass
        # TODO: exit on error

    # chose backup code auth
    print("Chose auth with backup code...")
    backup_code = driver.find_element(By.XPATH, BACKUP_CODE_XPATH)
    next_btn = driver.find_element(By.XPATH, NEXT_BUTTON_XPATH)
    # chose use backup code
    ActionChains(driver).move_to_element(backup_code).click().perform()
    # click next
    ActionChains(driver).move_to_element(next_btn).click().perform()
    time.sleep(10.0)

    # input backup code
    print("Inputting backup code...")
    backup_code_enter = driver.find_element(By.XPATH, INPUT_BACKUP_CODE_XPATH)
    ActionChains(driver).move_to_element(backup_code_enter).click().send_keys(BACKUP_CODE).perform()
    next_btn = driver.find_element(By.XPATH, NEXT_BUTTON_XPATH)
    ActionChains(driver).move_to_element(next_btn).click().perform()
    time.sleep(10.0)

    # choice no ads
    try:
        no_ads = driver.find_element(By.XPATH, "//*[text()='Keep less relevant ads']")
        ActionChains(driver).move_to_element(no_ads).click().perform()
    except NoSuchElementException:
        print("don't need to chose Ads options")

    try:
        driver.find_element(By.XPATH, "//*[text()='Welcome to Twitter!']")
        return True
    except NoSuchElementException:
        print("Login failed!")
        driver.save_screenshot("login-failed.png")

    return False


def dump_cookies():
    cookies = driver.get_cookies()
    with open('cookies.json', 'w') as fout:
        fout.write(json.dumps(cookies, ensure_ascii=False))


def restore_cookies():
    driver.get("https://twitter.com")
    with open('cookies.json', 'r') as fin:
        cookies = json.load(fin)
    for cookie in cookies:
        driver.add_cookie(cookie)
    driver.refresh()


if __name__ == '__main__':
    # restore_cookies()
    driver.get(os.getenv("FAV_URL"))
    print('Wait for page loading...')
    time.sleep(10.0)
    print('Start download...')
    # download_images()
