import ast
import imaplib
import email
import re
import os
import urllib.request
import ssl
from PIL import Image
from PIL.ExifTags import TAGS
import hashlib
from gmplot import gmplot
import csv
import time
from math import floor

# 프로그램 수행시간 측정 시작!
start = time.time()

print('Program Start!!\n')

# imap 라이브러리 사용해 G-mail 서버 로그인
imap = imaplib.IMAP4_SSL('imap.gmail.com')
id = 'solmontea98@gmail.com'
pw = 'fzejdruhyrrgakwt'
imap.login(id, pw)

# for avoid warning
ssl._create_default_https_context = ssl._create_unverified_context

# 현재 작업 경로 읽어오기
NOW_PATH = os.getcwd()

# 다운받을 파일명 리스트
FILE_LIST = []

# 파싱 위한 정규표현식 리스트 ( Sender = 송신자 파싱, Link = 파일 링크 파싱, Url = url 정보 파싱 )
MAIL_SRC = 'fl0ckfl0ck@hotmail.com'
REGEX_EXPRESSION_SENDER = '[a-z\d]+([\.\_]?[a-z\d]+)+@[a-z\d]+(\.[a-z]+)+'
REGEX_EXPRESSION_LINK = "http(s):\/\/bit\.ly\/......."
REGEX_EXPRESSION_URL = 'long_url": ".*?"'
REGEX_EXPRESSION_ALTITUDE = 'elevation" :.*?,'
regex_sender = re.compile('{}'.format(REGEX_EXPRESSION_SENDER))
regex_link = re.compile('{}'.format(REGEX_EXPRESSION_LINK))
regex_url = re.compile('{}'.format(REGEX_EXPRESSION_URL))
regex_altitude = re.compile('{}'.format(REGEX_EXPRESSION_ALTITUDE))

# 구글맵 표시 위한 setting
gmap = gmplot.GoogleMapPlotter(30.2736, 127.0286, 5)  # 지도의 중심
gmap.apikey = "AIzaSyAeZncK824XkRpxhu7UHv9SrX9FUX-LAX4"


# 문자열의 인코딩 정보추출 후, 문자열, 인코딩 얻기
def findEncodingInfo(txt):
    info = email.header.decode_header(txt)
    s, encoding = info[0]
    return s, encoding


# 날짜 정보 formatting 함수
def convert_date(date):
    res = ""
    res += date[3]
    res += '-'

    if date[2] == 'Jun':
        res += '06'
    elif date[2] == 'Jul':
        res += '07'
    elif date[2] == 'Aug':
        res += '08'
    elif date[2] == 'Sep':
        res += '09'
    elif date[2] == 'Oct':
        res += '10'
    res += '-'

    res += date[1]
    return res


# 단축 url의 원래 url을 알아내는 함수
# 1. 단축 url 뒤에 '+' 를 붙인 url로 접속시 해당 original url에 대한 정보를 알아낼 수 있다. 이를 정규표현식을 이용해 파싱해온다.
# 2. 한글 인코딩을 중간에 복구해준다
def recover_bitly(url):
    url += '+'
    html = urllib.request.urlopen(url).read()

    koreanified_html = html.decode('utf-8')
    original_url = str(koreanified_html).encode('utf-8').decode('unicode_escape')


    original_url = re.search(regex_url, str(original_url)).group()
    return original_url[12:-1]


# 구글 맵 elevation api를 이용해 위도 경도 포함된 url에서 elevation 정보 받아옴
def find_elevation_info(url):
    html = urllib.request.urlopen(url).read()
    elevation = re.search(regex_altitude, str(html)).group()
    return elevation[13:-1]


# Main Logic
# 1. Gmail을 열어 'fl0ckfl0ck@hotmail.com' 으로부터 온 이메일을 걸러낸다.
# 2. 걸러낸 이메일에서 단축 url에 해당하는 부분을 정규표현식을 이용해 파싱한다.
# 3. 파일 내부의 EXIF 데이터를 읽어와 csv 파일로 저장한다
# 4. 읽어온 EXIF 정보 중 위도, 경도 데이터를 이용하여 구글 맵에 표현한다


# 1.
print('Step 1. Gmail을 열어 \'fl0ckfl0ck@hotmail.com\' 으로부터 온 이메일을 걸러낸다.')

# 받은 편지함
imap.select('inbox')

# 받은 편지함 모든 메일 검색
resp, data = imap.uid('search', None, 'All')

# 여러 메일 읽기 (반복)
all_email = data[0].split()

global ctr
ctr = 0

# 모든 이메일에 대해 반복!
for mail in all_email:
    ctr = ctr + 1

    # 진행 과정 display
    print('MAIL {}/{} processed...'.format(ctr, len(all_email)))
    # fetch 명령을 통해서 메일 가져오기 (RFC822 Protocol)
    result, data = imap.uid('fetch', mail, '(RFC822)')

    # 사람이 읽기 힘든 Raw 메세지 (byte)
    raw_email = data[0][1]

    # 메시지 처리(email 모듈 활용)
    email_message = email.message_from_bytes(raw_email)

    # sender 정보 파싱
    try:
        sender = regex_sender.search(email_message['From']).group()

    except AttributeError:
        continue

    # 만약 flockflock 으로부터 온 메일이 아니라면 pass!
    if sender != MAIL_SRC:
        continue

    # 날짜정보 파싱
    date = email_message['Date'].split(' ')

    # 이메일 본문 내용 확인
    if email_message.is_multipart():
        for part in email_message.get_payload():
            bytes = part.get_payload(decode=True)
            encode = part.get_content_charset()

            # 단축 url에 해당하는 부분 파싱
            links = re.search(regex_link, str(bytes, encode)).group()

            # 첨부파일 리스트에 (파일 단축 url, 날짜 정보) 추가
            FILE_LIST.append([links, date])

# 2.
print('\n2. 걸러낸 이메일에서 단축 url에 해당하는 부분을 정규표현식을 이용해 파싱한다.')


# 2차원 리스트인 첨부파일 목록 ( [파일 url, 시간 정보] ) 에서 중복된 파일을 제거한다

def convert_str(x):
    if type(x) is str:
        return "'" + x + "'"
    else:
        return str(x)


COMPRESSED_FILE_LIST = list(map(ast.literal_eval, set(map(convert_str, FILE_LIST))))

# COMPRESSED_FILE_LIST의 파일들에 대해 날짜 정보와 같은 이름의 폴더 생성 후 폴더 안에 해당 url에 해당하는 파일 다운받아 저장
for i in range(len(COMPRESSED_FILE_LIST)):
    print('downloading files {}/{}\n'.format(i, len(COMPRESSED_FILE_LIST)))
    folder_name = convert_date(COMPRESSED_FILE_LIST[i][1])

    if not (os.path.isdir(folder_name)):
        os.makedirs(os.path.join(folder_name))

    os.chdir(NOW_PATH + '/' + folder_name)
    urllib.request.urlretrieve(COMPRESSED_FILE_LIST[i][0], COMPRESSED_FILE_LIST[i][0][15:] + '.jpeg')

    # 상위 폴더로 복귀
    os.chdir(NOW_PATH)

# 이메일 관련 imap 객체 종료 및 로그아웃
imap.close()
imap.logout()

print('File Download Complete\n')

##################################################################################################################

# 3
print('\n3. 파일 내부의 EXIF 데이터를 읽어와 csv 파일로 저장한다')

global INDEX
INDEX = 1


# 폴더 경로 입력시 해당 폴더 및 하위 폴더의 jpeg 파일들을 읽어와 각 파일의 exif 정보를 이용해 csv 파일을 만드는 함수
def Make_CSV(path_dir):
    # 카운터 변수
    global INDEX

    # 해당 폴더 경로 내의 모든 파일 탐색
    for (path, dirs, files) in os.walk(path_dir):

        # 파일마다 작업 수행
        for file in files:
            filename = (path + '/' + file)
            extension = filename.split('.')[-1]

            # jpeg 파일 아니면 pass!!
            if extension != 'jpeg':
                continue

            # 각 파일들의 주요 정보 & EXIF 정보 추출 후 CSV 파일에 저장
            for f in [filename]:

                # PIL 패키지의 Image 라이브러리의 _getexif() 함수 통해 exif 정보 추출
                im = Image.open(f)
                info = im._getexif()
                exif = {}

                # 0x9003 = 사진 메타데이터 속 exif 정보 중 created time(ctime) 의 위치
                try:
                    ctime = info[0x9003]

                except KeyError:
                    ctime = 'Unknown'

                # 단축 URL
                shortened_url = ('https://bit.ly/{}'.format(file))[:-5]

                # Full URL
                original_url = recover_bitly(shortened_url)

                # Actual File name
                original_file = original_url.split('/')[3]

                # MD5
                f = open(filename, 'rb')
                MD5_hash = hashlib.md5(f.read()).hexdigest()

                # SHA1
                SHA1_hash = hashlib.sha1(f.read()).hexdigest()

                # exif 데이터에서 위도, 경도 계산하는 부분
                try:
                    for tag, value in info.items():
                        decoded = TAGS.get(tag, tag)
                        exif[decoded] = value

                    # exif 데이터에서 gps 추출 (default = 동경, 북경)
                    # exifGPS = [ GPS Version, GPS Latitude direction, GPS Latitude, GPS Longitude direction, GPS Longitude, GPS Altitude Ref, GPS Altitude (해수면고도) ]
                    exifGPS = exif['GPSInfo']

                    latitude = exifGPS[2]
                    longitude = exifGPS[4]
                    Altitude = exifGPS[6]

                    # 위도 경도 계산
                    latDeg = latitude[0]
                    latMin = latitude[1]
                    latSec = latitude[2]
                    lonDeg = longitude[0]
                    lonMin = longitude[1]
                    lonSec = longitude[2]

                    Lat_info = (latDeg + (latMin + latSec / 60.0) / 60.0)

                    # 만약 남경이라면 역으로 계산
                    if exifGPS[1] == 'S':
                        Lat_info = Lat_info * -1

                    # 만약 서경이라면 역으로 계산
                    Lon_info = (lonDeg + (lonMin + lonSec / 60.0) / 60.0)
                    if exifGPS[3] == 'W':
                        Lon_info = Lon_info * -1

                    if exifGPS[5] == 1:
                        Altitude = Altitude * -1

                    # 실제 google_map에서 위도, 경도를 통해 불러온 해당 지점의 해발고도 (elevation 정보) 와 exif 데이터 속의 해발고도를 비교해서 조작여부를 판별
                    altitude_request_url = 'https://maps.googleapis.com/maps/api/elevation/json?locations={},{}&key={}'.format(
                        Lat_info, Lon_info, gmap.apikey)

                    # 실제 해발고도와 Exif 의 해발고도가 10m 이상 차이날 경우 조작된 사진으로 판별
                    if eval(find_elevation_info(altitude_request_url)) - int(floor(Altitude)) > 10 or eval(
                            find_elevation_info(altitude_request_url)) - int(floor(Altitude)) < -10:
                        print('File No.{} is modified'.format(INDEX))

                    # CSV 파일에 GPS 정보 입력
                    CSV_write.write(
                        str(INDEX) + "," + str(ctime) + "," + str(shortened_url) + "," + str(original_url) + "," + str(
                            original_file) + "," + str(Lat_info) + "," + str(Lon_info) + "," + str(Altitude) + "," + str(
                            MD5_hash) + "," + str(SHA1_hash) + "\n")

                    INDEX = INDEX + 1

                except:
                    CSV_write.write((str(INDEX)) + "," + str(ctime) + "," + str(shortened_url) + "," + str(
                        original_url) + "," + str(original_file) + "," + "NOT" + "," + "NOT" + "," + "NOT" + "," + str(
                        MD5_hash) + "," + str(SHA1_hash) + "\n")
                    INDEX = INDEX + 1
                    pass

            f.close()


CSV_write = open("Image_GPS.csv", 'w')
CSV_write.write(
    "NUMBER," + "Date," + "Shortened URL," + "Full URL," + "FileName," + "Latitude," + "Longitude," + "Altitude," + "MD5," + "SHA1," + "\n")

Make_CSV(NOW_PATH)
CSV_write.close()

print('CSV Making Complete!\n')

#####################################################################################################################################################################

# 4
print('\n 4. 읽어온 EXIF 정보 중 위도, 경도 데이터를 이용하여 구글 맵에 표현한다')

# 읽어올 파일 이름
filename = 'Image_GPS.csv'

# 마커로 표시할 위도, 경도 정보
latitudes, longitudes = [], []

# CSV 파일을 열어 각 행의 6, 7열에 있는 위도 경도 정보를 가져와 위의 리스트에 추가한다!
with open(filename) as f:
    reader = csv.reader(f)

    # 첫줄은 메타데이터이므로 점프!
    next(reader)

    for row in reader:

        try:
            latitudes.append(float(row[5]))
            longitudes.append(float(row[6]))

        except ValueError:
            pass

# Scatter Drawing
gmap.scatter(latitudes, longitudes, '#FF0000', size=20, marker=True)
gmap.plot(latitudes, longitudes, 'cornflowerblue', edge_width=3.0)

# Draw
gmap.draw("Image_GPS.html")

# FINISH
print('\n Program Finish --> Elapsed Time : {}'.format(time.time() - start))
