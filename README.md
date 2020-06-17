# Novel Scraper

**A python script for scraping novels from https://www.biquge5200.com**

## Requirements Installation

```
cd scraper
pip install -r requirements.txt
```

## Set Mongodb Credentials

cp Configs.example.py Configs.py
And set the constants in Configs.py

## Usage

First cd to scraper dir

```
cd scraper
```

Download a novel from url

```
python main.py -u URL
```

Download some novels from a list of urls

```
python main.py -f URL_LIST.txt
```

Search and download a novel

```
python main.py -s KEYWORDS
```

Download all novels from biquge

```
python main.py -D
```

If you want to download concurrently, add -c argument

```
python main.py -u URL -c
```

## License

MIT
