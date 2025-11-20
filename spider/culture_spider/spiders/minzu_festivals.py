
# -*- coding: utf-8 -*-
import re, hashlib
from urllib.parse import urljoin, urlparse
import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from ..items import FestivalItem
from w3lib.url import canonicalize_url

ETHNIC_WHITELIST = [
    "汉族","壮族","满族","回族","苗族","维吾尔族","土家族","彝族","蒙古族","藏族","布依族","侗族","瑶族",
    "朝鲜族","白族","哈尼族","哈萨克族","黎族","傣族","畲族","僳僳族","仡佬族","东乡族","高山族","拉祜族",
    "水族","佤族","纳西族","羌族","土族","仫佬族","锡伯族","柯尔克孜族","达斡尔族","景颇族","毛南族","撒拉族",
    "布朗族","塔吉克族","阿昌族","普米族","鄂温克族","怒族","京族","基诺族","德昂族","保安族","俄罗斯族",
    "裕固族","乌孜别克族","门巴族","鄂伦春族","独龙族","塔塔尔族","赫哲族","珞巴族","维族","藏民","彝民","傣民","苗民","畲民","土族人","京族人"
]
ETHNIC_RE = re.compile("|".join(map(re.escape, ETHNIC_WHITELIST)))
REGION_RE = re.compile(r"(?:[京津沪渝][市]|[\u4e00-\u9fa5]{2,7}(?:省|自治区|市|州|盟)|[\u4e00-\u9fa5]{2,7}(?:县|旗|区|镇|乡|村))")
CALENDAR_KEYWORDS = ["农历","阴历","公历","阳历","伊斯兰教历","回历","藏历","傣历","苗历","彝历"]
CALENDAR_RE = re.compile("|".join(map(re.escape, CALENDAR_KEYWORDS)))
DATE_RULE_RE = re.compile(
    r"(?:农历|阴历|公历|阳历|伊斯兰教历|回历|藏历|傣历|苗历|彝历)?"
    r"[^。；，,\n]{0,40}?"
    r"(?:正月|腊月|三月三|泼水节|元宵|清明|端午|中秋|重阳|初一|十五|\d+月\d+日|\d+月|每年)"
    r"[^。；，,\n]{0,15}?(?:前后|期间|当日|这天|前夕|之日|当天)?"
)
DATE_ANY_RE = re.compile(r"(?P<y>20\d{2})[-./年](?P<m>\d{1,2})[-./月](?P<d>\d{1,2})日?")
DATE_URL_RE1 = re.compile(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/")
DATE_URL_RE2 = re.compile(r"/t(20\d{2})(\d{2})(\d{2})")

class MinzuFestivalsSpider(CrawlSpider):
    name = "minzu_festivals"
    allowed_domains = ["www.minwang.com.cn","minwang.com.cn","w.minwang.com.cn","www.mzzyk.com","mzzyk.com","m.mzzyk.com"]
    start_urls = [
        "http://www.minwang.com.cn/mzwhzyk/674771/682393/index.html",
        "https://w.minwang.com.cn/mzwhzyk/674771/682393/index.html",
        "https://www.mzzyk.com/mzwhzyk/674771/682393/index.html",
    ]

    rules = (
        Rule(LinkExtractor(allow=(r"/mzwhzyk/674771/682393/(?:index|index_\d+)?\.html")), follow=True),
        Rule(LinkExtractor(allow=(
            r"/mzwhzyk/674771/682393/\d+/\d+/(?:\d+/)?\d+/?index\.html",
            r"/mzwhzyk/674771/682393/\d+/\d+/\d+/\d+\.html",
            r"/mzwhzyk/674771/682393/[^?#]+\.html")), callback="parse_detail", follow=True),
    )

    custom_settings = {"FEEDS": {"out.ndjson":{"format":"jsonlines","encoding":"utf-8","overwrite":True}}}

    def _extract_publish_date(self, resp):
        candidates = [
            resp.css("meta[property='article:published_time']::attr(content)").get(),
            resp.css("meta[name='PubDate']::attr(content)").get(),
            resp.css(".pubtime::text, .time::text, .info::text, .source::text").get(),
            " ".join(resp.css(".info *::text, .article-info *::text").getall() or [])
        ]
        for c in candidates:
            if not c: continue
            m = DATE_ANY_RE.search(c)
            if m:
                y, mth, d = m.group("y"), m.group("m"), m.group("d")
                return f"{y}-{int(mth):02d}-{int(d):02d}"
        m1 = DATE_URL_RE1.search(resp.url)
        if m1:
            y,mth,d = m1.groups()
            return f"{y}-{int(mth):02d}-{int(d):02d}"
        m2 = DATE_URL_RE2.search(resp.url)
        if m2:
            y,mth,d = m2.groups()
            return f"{y}-{int(mth):02d}-{int(d):02d}"
        return None

    def _extract_text(self, resp):
        paras = resp.css("article p::text, .article p::text, .content p::text, .con p::text, .detail p::text, .TRS_Editor p::text, p::text").getall()
        return "\\n".join([p.strip() for p in paras if p and p.strip()])

    def _extract_media(self, resp):
        imgs = []
        for img in resp.css("article img, .article img, .content img, .con img, img"):
            src = img.attrib.get("src") or img.attrib.get("data-src") or img.attrib.get("data-original")
            if not src: continue
            imgs.append({"type":"image","url":urljoin(resp.url, src),"caption":(img.attrib.get("alt") or "").strip()})
        return imgs

    def parse_detail(self, resp):
        if "/mzwhzyk/674771/682393/" not in resp.url:
            return
        item = FestivalItem()
        item["url"] = resp.url
        item["site_name"] = "中国民族文化资源库"
        item["lang"] = (resp.css("html::attr(lang)").get() or "zh").lower()
        item["canonical_url"] = canonicalize_url(resp.css("link[rel='canonical']::attr(href)").get() or resp.url)

        title = resp.css("h1::text, h2.title::text, .article-title::text").get() or resp.css("title::text").get() or ""
        item["title"] = title.strip()
        item["publish_date"] = self._extract_publish_date(resp)
        item["author"] = "".join(resp.css(".author::text, .source a::text, .source::text, .info::text").getall()).strip() or None
        text = self._extract_text(resp)
        item["content_text"] = text
        item["media"] = self._extract_media(resp)

        t = f"{item['title']}。{text}"
        names = re.findall(r"([\\u4e00-\\u9fa5A-Za-z·]{1,20}节)", t)
        names = list(dict.fromkeys(names)) if names else ([item["title"]] if item["title"] else [])
        item["festival_names"] = names or None

        buf = f"{title} {text}"
        e = list(set(ETHNIC_RE.findall(buf)))
        item["ethnic_groups"] = e or None

        regs = list(set(REGION_RE.findall(text)))
        regs = [r for r in regs if len(r) >= 2]
        item["regions"] = regs or None

        cal = None
        mcal = CALENDAR_RE.search(t)
        if mcal: cal = mcal.group(0)
        mrule = DATE_RULE_RE.search(t)
        item["calendar_type"] = cal
        item["date_rule"] = mrule.group(0) if mrule else None

        item["category_path"] = urlparse(resp.url).path.replace("/mzwhzyk/674771/682393/","").strip("/")
        base = (item["title"] or "") + (item["content_text"] or "")
        item["content_hash"] = hashlib.md5(base.encode("utf-8")).hexdigest()
        return item
