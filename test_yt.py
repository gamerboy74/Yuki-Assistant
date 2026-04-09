import urllib.request, re, urllib.parse
req = urllib.request.Request('https://www.youtube.com/results?search_query=arijit+singh', headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8', errors='ignore')
ids = re.findall(r'"videoId":"([^"]{11})"', html)
print(ids[:5])
