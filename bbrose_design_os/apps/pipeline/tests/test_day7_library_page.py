"""Day 7 §5: the Library page on the index — kinds with counts, previews, search by words and colour, filters by rights tier
and surface, the excluded fonts under their heading, a detail view with rights and "used in"."""
from django.contrib.auth.models import User
from django.test import TestCase
from apps.dashboard import materials_library as ml


class Day7LibraryPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("day7", "d7@example.com", "pw")
        self.client.force_login(self.user)

    def test_the_page_lists_kinds_with_counts_and_the_excluded_fonts_heading(self):
        r = self.client.get("/dashboard/materials/")
        assert r.status_code == 200
        body = r.content.decode()
        counts = ml.index_counts()
        assert "pattern (%d)" % dict(counts["kinds"])["pattern"] in body and "font (%d)" % dict(counts["kinds"])["font"] in body
        assert ml.EXCLUDED_HEADING in body and "%d excluded fonts" % counts["tiers"]["excluded"] in body

    def test_filters_by_kind_tier_and_surface_and_searches_words_and_colour(self):
        found = ml.search_index(kind="pattern", tier="house", surface="carton", q="gold")
        assert found["n"] and all(m["kind"] == "pattern" and m["tier"] == "house" and "carton" in m["surfaces"] for m in found["rows"])
        from apps.pipeline.services import materials_retrieval as mr
        for m in found["rows"]:                       # the card truncates tags; the match is checked on the full index row
            row = mr.index_row(m["sha"])
            hay = " ".join((row.get("tags") or []) + (row.get("style") or []) + [row.get("subject") or ""] + (row.get("text_seen") or []) + [row.get("name") or ""]).lower()
            assert "gold" in hay, m["sha"]
        deco = ml.search_index(q="art deco")
        assert deco["n"] and deco["rows"][0]["sha"]
        colour = ml.search_index(kind="pattern", colour="#C9A227")
        assert colour["colour"] == "C9A227" and colour["n"] and colour["rows"][0]["de"] is not None and colour["rows"][0]["de"] <= ml.COLOUR_MATCH_DE
        excluded = ml.search_index(tier="excluded")
        assert excluded["n"] == ml.index_counts()["tiers"]["excluded"] and all(m["excluded"] and m["kind"] == "font" for m in excluded["rows"])
        r = self.client.get("/dashboard/materials/?tier=excluded")
        assert r.status_code == 200 and "Excluded font — no licence evidence" in r.content.decode()

    def test_the_detail_view_shows_rights_metadata_and_used_in_and_the_preview_is_hash_named(self):
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask, ConceptReference
        row = ml.search_index(kind="pattern", q="gold")["rows"][0]
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="gold carton", created_by=self.user)
        ConceptReference.objects.create(task=task, source_type="MATERIAL_LIBRARY", library_item_id="materials:" + row["sha"], title="t",
                                        description="role: pattern · pattern", image_root="previews", image_path=row["sha"] + ".png")
        r = self.client.get("/dashboard/materials/%s/" % row["sha"])
        assert r.status_code == 200
        body = r.content.decode()
        assert "Rights" in body and "D-D7-1" in body and "Used in" in body and "Design %d" % task.pk in body and row["sha"] in body
        p = self.client.get("/dashboard/materials/previews/%s.png" % row["sha"])
        if ml.preview_file(row["sha"]):
            assert p.status_code == 200 and p["Content-Type"] == "image/png"
        else:
            assert p.status_code == 404
        assert self.client.get("/dashboard/materials/%s/" % ("0" * 64)).status_code == 404
        assert self.client.get("/dashboard/materials/previews/%s.png" % ("0" * 64)).status_code == 404
