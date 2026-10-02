import unittest
from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DocumentParser(HTMLParser):
    """Collect enough document structure to test UI contracts without dependencies."""

    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.nodes = []
        self.stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": [], "text": []}
        if self.stack:
            self.stack[-1]["children"].append(node)
        self.nodes.append(node)
        if tag not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.text.append(data)
        if self.stack:
            self.stack[-1]["text"].append(data)


def contains_tag(node, tag):
    return node["tag"] == tag or any(contains_tag(child, tag) for child in node["children"])


class HomeDistributionChannelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        cls.document = DocumentParser()
        cls.document.feed(cls.source)

    def test_home_channels_do_not_claim_unverified_connections(self):
        page_text = " ".join(self.document.text)
        self.assertTrue(
            "Distribution channels" in page_text,
            "Home should use a neutral distribution-channel heading.",
        )
        self.assertFalse(
            "Connected distribution channels" in page_text,
            "Home must not imply the social accounts are connected.",
        )

    def test_home_channels_are_logo_only_accessible_platform_chips(self):
        chips = [
            node for node in self.document.nodes
            if "soc-item" in node["attrs"].get("class", "").split()
        ]
        expected = {
            "youtube": "YouTube",
            "x": "X",
            "facebook": "Facebook",
            "linkedin": "LinkedIn",
            "instagram": "Instagram",
            "email": "Email",
        }
        self.assertEqual(set(expected), {node["attrs"].get("data-channel") for node in chips})
        for chip in chips:
            channel = chip["attrs"].get("data-channel")
            with self.subTest(channel=channel):
                self.assertEqual("span", chip["tag"])
                self.assertEqual(expected[channel], chip["attrs"].get("aria-label"))
                self.assertTrue(contains_tag(chip, "svg"))
                self.assertFalse(any(
                    "soc-label" in child["attrs"].get("class", "").split()
                    for child in chip["children"]
                ))
        soc = next(
            node for node in self.document.nodes
            if "soc" in node["attrs"].get("class", "").split()
        )
        self.assertFalse(contains_tag(soc, "a"))


class SocialStudioStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        cls.document = DocumentParser()
        cls.document.feed(cls.source)

    def test_create_and_grow_has_one_combined_social_destination(self):
        nav_links = [
            node for node in self.document.nodes
            if node["tag"] == "a" and node["attrs"].get("data-view")
        ]
        nav_destinations = {node["attrs"]["data-view"] for node in nav_links}
        self.assertIn("social-studio", nav_destinations)
        self.assertFalse(nav_destinations.intersection({"facebook", "instagram", "linkedin"}))
        view_ids = {
            node["attrs"].get("id") for node in self.document.nodes
            if node["tag"] == "section" and "view" in node["attrs"].get("class", "").split()
        }
        self.assertIn("social-studio", view_ids)
        self.assertFalse(view_ids.intersection({"facebook", "instagram", "linkedin"}))

    def test_social_studio_accepts_one_brief_and_multiple_platforms(self):
        checkboxes = {
            node["attrs"].get("value") for node in self.document.nodes
            if node["tag"] == "input"
            and node["attrs"].get("type") == "checkbox"
            and node["attrs"].get("name") == "socialPlatform"
        }
        self.assertEqual({"facebook", "instagram", "linkedin", "x"}, checkboxes)
        ids = {node["attrs"].get("id") for node in self.document.nodes}
        self.assertIn("socialBrief", ids)
        self.assertIn("createSocialDrafts", ids)
        self.assertIn("socialDraftOutputs", ids)


class LocalContentOrganizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        cls.logic = (PROJECT_ROOT / "content-organizers.js").read_text(encoding="utf-8")
        cls.document = DocumentParser()
        cls.document.feed(cls.source)

    def nodes_with_id(self, element_id):
        return [
            node for node in self.document.nodes
            if node["attrs"].get("id") == element_id
        ]

    def options_for(self, element_id):
        select = self.nodes_with_id(element_id)
        self.assertEqual(1, len(select), f"Expected one #{element_id} control.")
        return {
            node["attrs"].get("value")
            for node in select[0]["children"]
            if node["tag"] == "option"
        }

    def test_social_studio_distinguishes_x_post_thread_and_article(self):
        self.assertEqual({"post", "thread", "article"}, self.options_for("socialXFormat"))
        self.assertEqual(1, len(self.nodes_with_id("socialDraftOutputs")))

    def test_multi_day_pack_is_inside_social_studio_and_has_local_asset_slots(self):
        social_view = self.nodes_with_id("social-studio")
        self.assertEqual(1, len(social_view))
        self.assertTrue(contains_tag(social_view[0], "form"))
        for element_id in ("multiDayPackForm", "multiDayPackStatus", "multiDayPackOutputs"):
            with self.subTest(element_id=element_id):
                self.assertEqual(1, len(self.nodes_with_id(element_id)))
        self.assertEqual({"2", "3", "7"}, self.options_for("multiDayDays"))
        platforms = {
            node["attrs"].get("value") for node in self.document.nodes
            if node["tag"] == "input"
            and node["attrs"].get("type") == "checkbox"
            and node["attrs"].get("name") == "multiDayPlatform"
        }
        self.assertEqual({"facebook", "instagram", "linkedin", "x", "blog", "email"}, platforms)
        self.assertEqual({"post", "thread", "article"}, self.options_for("multiDayXFormat"))

    def test_repurpose_has_source_text_reference_and_explicit_output_formats(self):
        for element_id in ("repurposeForm", "repurposeSourceText", "repurposeSourceUrl", "repurposeFormat", "createRepurposeDraft", "repurposeDraftOutputs"):
            with self.subTest(element_id=element_id):
                self.assertEqual(1, len(self.nodes_with_id(element_id)))
        self.assertEqual(
            {
                "x-post", "x-thread", "x-article", "facebook-post",
                "instagram-caption", "linkedin-post", "linkedin-article",
                "blog-article", "email",
            },
            self.options_for("repurposeFormat"),
        )

    def test_organizer_ui_explains_local_only_no_publish_behavior(self):
        page_text = " ".join(self.document.text).lower()
        self.assertIn("saved in this browser", page_text)
        self.assertTrue("not fetched" in page_text, "The optional source URL must be labeled reference-only.")
        self.assertTrue("nothing is published" in page_text, "Organizer drafts must never claim to publish.")
        self.assertIn('<script src="content-organizers.js"></script>', self.source)
        self.assertTrue("contenthub.localorganizers.v1" in self.logic.lower(), "Organizer drafts must use local browser storage.")
        self.assertNotIn("fetch(", self.logic.lower(), "Local organizers must not call remote or provider APIs.")


class SharedContentWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        cls.records_logic = (PROJECT_ROOT / "content-records.js").read_text(encoding="utf-8") if (PROJECT_ROOT / "content-records.js").exists() else ""
        cls.organizer_logic = (PROJECT_ROOT / "content-organizers.js").read_text(encoding="utf-8")
        cls.document = DocumentParser()
        cls.document.feed(cls.source)

    def nodes_with_id(self, element_id):
        return [node for node in self.document.nodes if node["attrs"].get("id") == element_id]

    def test_shared_review_queue_is_brand_scoped_and_not_seeded_with_samples(self):
        self.assertEqual(1, len(self.nodes_with_id("activeBrandSelect")))
        self.assertEqual(1, len(self.nodes_with_id("appr-body")))
        approvals_body = self.nodes_with_id("appr-body")[0]
        self.assertFalse(any(child["tag"] == "tr" for child in approvals_body["children"]))
        self.assertIn("/api/content?brand=", self.records_logic)
        self.assertIn("Needs Review", self.records_logic)

    def test_calendar_has_month_navigation_and_uses_dated_shared_records(self):
        for element_id in ("calendarTitle", "calendarPrev", "calendarNext", "cal"):
            with self.subTest(element_id=element_id):
                self.assertEqual(1, len(self.nodes_with_id(element_id)))
        self.assertIn("targetDate", self.records_logic)
        self.assertIn("/api/content?brand=", self.records_logic)

    def test_submission_dialog_and_local_draft_submit_actions_are_explicit(self):
        for element_id in ("contentSubmitDialog", "contentSubmitDate", "contentSubmitForm"):
            with self.subTest(element_id=element_id):
                self.assertEqual(1, len(self.nodes_with_id(element_id)))
        self.assertIn("content-records.js", self.source)
        self.assertIn("submitDraft", self.records_logic)
        self.assertIn("Submit for review", self.organizer_logic)
        self.assertIn("Submit for review", self.source)


class ChannelEditorWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        cls.records_logic = (PROJECT_ROOT / "content-records.js").read_text(encoding="utf-8")
        editor_path = PROJECT_ROOT / "channel-editors.js"
        cls.editor_logic = editor_path.read_text(encoding="utf-8") if editor_path.exists() else ""
        cls.document = DocumentParser()
        cls.document.feed(cls.source)

    def nodes_with_id(self, element_id):
        return [node for node in self.document.nodes if node["attrs"].get("id") == element_id]

    def test_blog_reels_email_have_selected_brand_editor_and_shared_record_list(self):
        for channel in ("blog", "reels", "email"):
            with self.subTest(channel=channel):
                self.assertIn(f'data-channel-editor="{channel}"', self.source)
                self.assertEqual(1, len(self.nodes_with_id(f"{channel}EditorForm")))
                self.assertEqual(1, len(self.nodes_with_id(f"{channel}ContentRecords")))
                self.assertEqual(1, len(self.nodes_with_id(f"{channel}EditorStatus")))
        self.assertIn('<script src="channel-editors.js"></script>', self.source)
        self.assertIn("/api/content?brand=", self.editor_logic)
        self.assertIn("activeBrandSelect", self.editor_logic)

    def test_channel_handoff_is_approved_only_and_downloads_locally(self):
        self.assertIn("Approved", self.editor_logic)
        self.assertIn("new Blob(", self.editor_logic)
        self.assertIn("URL.createObjectURL", self.editor_logic)
        self.assertIn("download =", self.editor_logic)
        self.assertNotRegex(self.editor_logic, r"fetch\([^)]*https?://")
        self.assertNotIn("window.open", self.editor_logic)
        self.assertIn("does not move browser drafts or publish, schedule, or send content", self.source)

    def test_unsent_drafts_do_not_appear_in_the_approval_queue(self):
        self.assertIn("records.filter(record => record.status !== 'Draft')", self.records_logic)

    def test_edit_messages_explain_status_transitions_before_changes(self):
        for expected in (
            "Saving this Draft keeps it in Draft.",
            "Saving edits to a Needs Review record marks it Changes Requested; submit again after editing.",
            "Saving edits to a Changes Requested record keeps it Changes Requested until you submit again.",
            "Saving edits to an Approved record marks it Changes Requested; it will need review again.",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.editor_logic, f"Missing status transition notice: {expected}")

    def test_channel_starter_templates_and_hook_selectors_are_available(self):
        for channel in ("blog", "reels", "email"):
            with self.subTest(channel=channel):
                self.assertEqual(1, len(self.nodes_with_id(f"{channel}StarterTemplate")))
        self.assertEqual(1, len(self.nodes_with_id("reelsHookLibrary")))
        self.assertIn("TEMPLATES", self.editor_logic)
        self.assertIn("HOOK_LIBRARY", self.editor_logic)
        self.assertIn("data-channel-apply-template", self.source)
        self.assertIn("data-channel-apply-hook", self.source)


class ReportingViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        reporting_path = PROJECT_ROOT / "reporting.js"
        cls.reporting_logic = reporting_path.read_text(encoding="utf-8") if reporting_path.exists() else ""
        cls.document = DocumentParser()
        cls.document.feed(cls.source)

    def nodes_with_id(self, element_id):
        return [node for node in self.document.nodes if node["attrs"].get("id") == element_id]

    def test_reporting_view_is_brand_scoped_and_source_driven(self):
        self.assertEqual(1, len(self.nodes_with_id("reporting")))
        self.assertEqual(1, len(self.nodes_with_id("reportingStatus")))
        self.assertEqual(1, len(self.nodes_with_id("reportingSources")))
        self.assertIn('<script src="reporting.js"></script>', self.source)
        self.assertIn("/api/reporting/sources", self.reporting_logic)
        self.assertIn("/api/reporting/gsc?brand=", self.reporting_logic)
        self.assertIn("activeBrandSelect", self.reporting_logic)

    def test_reporting_does_not_display_unverified_placeholder_figures(self):
        page_text = " ".join(self.document.text).lower()
        for placeholder in ("august report", "24.1k", "3.2%", "8.9k", "312 reads"):
            with self.subTest(placeholder=placeholder):
                self.assertNotIn(placeholder, page_text)

    def test_reporting_explains_verified_read_only_and_not_connected_states(self):
        page_text = " ".join(self.document.text).lower()
        self.assertIn("read-only", page_text)
        self.assertIn("not connected", self.reporting_logic.lower())
        self.assertNotRegex(self.reporting_logic, r"fetch\([^)]*https?://")
        self.assertIn("verified", self.reporting_logic)

    def test_reporting_loads_pagespeed_and_mailerlite_read_only(self):
        self.assertIn("/api/reporting/pagespeed", self.reporting_logic)
        self.assertIn("/api/reporting/mailerlite", self.reporting_logic)
        self.assertTrue(self.reporting_logic.count("/api/reporting/gsc") >= 1)
        self.assertNotRegex(self.reporting_logic, r"MAILERLITE_API_KEY")
        self.assertNotRegex(self.reporting_logic, r"Bearer [A-Za-z0-9]")


class BrandProfileSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        profile_path = PROJECT_ROOT / "brand-profiles.js"
        cls.profile_logic = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
        cls.document = DocumentParser()
        cls.document.feed(cls.source)

    def nodes_with_id(self, element_id):
        return [node for node in self.document.nodes if node["attrs"].get("id") == element_id]

    def test_selected_brand_has_an_editable_complete_profile_in_settings(self):
        for element_id in (
            "brandProfileForm",
            "brandProfileVoiceStyle",
            "brandProfileAudience",
            "brandProfileOfferAndLinks",
            "brandProfileCtaStyle",
            "brandProfileNeverUse",
            "brandProfileContentPillars",
            "brandProfilePositioning",
            "brandProfileSourceFiles",
            "brandProfileStatus",
            "resetBrandProfile",
        ):
            with self.subTest(element_id=element_id):
                self.assertEqual(1, len(self.nodes_with_id(element_id)))
        self.assertIn("activeBrandSelect", self.profile_logic)
        self.assertIn("/api/brand-profile?brand=", self.profile_logic)
        self.assertIn("method: 'PUT'", self.profile_logic)
        self.assertIn("method: 'DELETE'", self.profile_logic)
        self.assertNotIn("localStorage", self.profile_logic)

    def test_profile_scope_and_source_file_behavior_are_explained(self):
        self.assertIn("brand-profiles.js", self.source)
        self.assertIn("Source Markdown files are unchanged", self.source)
        self.assertIn("Content Hub-only", self.source)


if __name__ == "__main__":
    unittest.main()
