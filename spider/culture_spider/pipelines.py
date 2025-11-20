# culture_spider/pipelines.py
import json
import pymysql
from datetime import datetime
from scrapy.exceptions import DropItem

# 同时支持两种 Item（按需导入）
from .items import FestivalItem, WikiItem  # 如果暂时没有 WikiItem，可先注释

def _json_dumps(x):
    return json.dumps(x, ensure_ascii=False) if x is not None else None


class DedupInlinePipeline:
    """基于 canonical_url + content_hash 的轻量去重（仅对单次运行生效）"""
    seen = set()
    def process_item(self, item, spider):
        url = item.get("canonical_url") or item.get("url")
        key = (url, item.get("content_hash"))
        if not url:
            raise DropItem("missing url")
        if key in self.seen:
            raise DropItem("duplicate content by canonical_url+hash")
        self.seen.add(key)
        return item


class MySQLStorePipeline:
    """写入 cultural_resources / cultural_entities / entity_relationships"""
    def open_spider(self, spider):
        self.conn = pymysql.connect(
            host=spider.settings.get("MYSQL_HOST"),
            port=spider.settings.getint("MYSQL_PORT", 3306),
            user=spider.settings.get("MYSQL_USER"),
            password=spider.settings.get("MYSQL_PASSWORD"),
            database=spider.settings.get("MYSQL_DB"),
            charset=spider.settings.get("MYSQL_CHARSET", "utf8mb4"),
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )
        self.cur = self.conn.cursor()

    def close_spider(self, spider):
        try:
            self.conn.commit()
        finally:
            self.cur.close()
            self.conn.close()

    # ---------- 公共工具 ----------
    def _ping(self):
        try:
            self.conn.ping(reconnect=True)
        except Exception:
            pass

    def _upsert_resource(self, *, title, resource_type, file_format,
                         source_from, source_url, content_feature_data):
        self.cur.execute(
            """
            INSERT INTO cultural_resources
              (title, resource_type, file_format, source_from, source_url,
               content_feature_data, version, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,1,NOW(),NOW())
            ON DUPLICATE KEY UPDATE
              title=VALUES(title),
              resource_type=VALUES(resource_type),
              file_format=VALUES(file_format),
              source_from=VALUES(source_from),
              version=IF(content_feature_data<>VALUES(content_feature_data), version+1, version),
              content_feature_data=VALUES(content_feature_data),
              updated_at=NOW()
            """,
            (title, resource_type, file_format, source_from, source_url, content_feature_data)
        )

    def _get_or_create_entity(self, name, etype, description=None, source=None,
                              cultural_region=None, related_images=None):
        if not name:
            return None
        self.cur.execute(
            "SELECT id FROM cultural_entities WHERE entity_name=%s AND entity_type=%s LIMIT 1",
            (name, etype)
        )
        row = self.cur.fetchone()
        if row:
            return row["id"]
        self.cur.execute(
            """
            INSERT INTO cultural_entities(
                entity_name, entity_type, description, source, cultural_region, related_images_url
            ) VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (name, etype, description, source, cultural_region, _json_dumps(related_images))
        )
        return self.cur.lastrowid

    def _insert_relationship(self, src_id, tgt_id, rtype, evidence=None, strength=None):
        if not src_id or not tgt_id:
            return
        self.cur.execute(
            "SELECT id FROM entity_relationships WHERE source_entity_id=%s AND target_entity_id=%s AND relationship_type=%s LIMIT 1",
            (src_id, tgt_id, rtype)
        )
        if self.cur.fetchone():
            return
        self.cur.execute(
            """
            INSERT INTO entity_relationships(
                source_entity_id, target_entity_id, relationship_type,
                relationship_strength, relationship_evidence
            ) VALUES (%s,%s,%s,%s,%s)
            """,
            (src_id, tgt_id, rtype, strength, evidence)
        )

    # ---------- 分支写入 ----------
    def process_item(self, item, spider):
        self._ping()

        # ===== A) 民族节日 =====
        if isinstance(item, FestivalItem):
            media_urls = [m.get("url") for m in (item.get("media") or []) if isinstance(m, dict) and m.get("url")]
            meta = {
                "publish_date": item.get("publish_date"),
                "calendar_type": item.get("calendar_type"),
                "date_rule": item.get("date_rule"),
                "ethnic_groups": item.get("ethnic_groups"),
                "regions": item.get("regions"),
                "canonical_url": item.get("canonical_url"),
                "content_hash": item.get("content_hash"),
                "images": media_urls,
            }
            content_feature_data = _json_dumps({
                "title": item.get("title"),
                "text": item.get("content_text"),
                "meta": meta
            })

            self._upsert_resource(
                title=item.get("title"),
                resource_type="文本",
                file_format="HTML",
                source_from=item.get("site_name") or "中国民族文化资源库",
                source_url=item.get("url"),
                content_feature_data=content_feature_data
            )

            # entities & relationships
            fest_ids, nation_ids, region_ids = [], [], []

            for fest in (item.get("festival_names") or []):
                fest = (fest or "").strip()
                if not fest:
                    continue
                desc = f"{item.get('title') or ''}\n{item.get('calendar_type') or ''} {item.get('date_rule') or ''}".strip()
                fid = self._get_or_create_entity(
                    name=fest, etype="节日",
                    description=desc or None, source=item.get("url"),
                    cultural_region="、".join(item.get("regions") or []) or None,
                    related_images=media_urls[:5] if media_urls else None
                )
                if fid:
                    fest_ids.append(fid)

            for nation in (item.get("ethnic_groups") or []):
                nation = (nation or "").strip()
                if not nation:
                    continue
                nid = self._get_or_create_entity(name=nation, etype="民族", source=item.get("url"))
                if nid:
                    nation_ids.append(nid)

            for region in (item.get("regions") or []):
                region = (region or "").strip()
                if not region:
                    continue
                rid = self._get_or_create_entity(name=region, etype="地点", source=item.get("url"))
                if rid:
                    region_ids.append(rid)

            evidence = item.get("url")
            for f in fest_ids:
                for n in nation_ids:
                    self._insert_relationship(f, n, "民族-节日", evidence=evidence)
                for r in region_ids:
                    self._insert_relationship(f, r, "地域-发生", evidence=evidence)

            self.conn.commit()
            return item

        # ===== B) 维基百科 =====
        if isinstance(item, WikiItem):
            content_feature_data = _json_dumps({
                "title": item.get("title"),
                "text": item.get("content_text"),
                "meta": {
                    "abstract": item.get("abstract"),
                    "infobox": item.get("infobox"),
                    "lang": item.get("lang")
                }
            })
            self._upsert_resource(
                title=item.get("title"),
                resource_type="百科",
                file_format="HTML",
                source_from="Wikipedia",
                source_url=item.get("url"),
                content_feature_data=content_feature_data
            )
            self.conn.commit()
            return item

        # 其它 Item 类型：直接丢回去（或 Drop）
        return item
