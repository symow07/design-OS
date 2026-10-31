"""Replaced when Home, Designs and the Library were switched to the chain's rounds (the owner's goal of 2026-10-29,
§0: "Keep Home, Designs and Library, switched to the chain engines"). Each block is the text as it stood at the commit
before the switch, unchanged, under the file and name it came from; the code that replaced it reads the rounds
(apps/dashboard/views.py round_card, round_board_context, _made_rounds; history_views.history_index;
context_processors.round_activity). Kept, never run: nothing imports this file."""


# ---- apps/dashboard/history_views.py :: history_index (lines 37–75)
@login_required
@require_GET
def history_index(request):
    """DESIGNS — C's (his pick of the executor's options, a691f56: "starting a design, the library and history are
    C's"): every design, newest first, by month, each a tile saying where it stands and opening its own page; found by
    its words (the brief, its records and decisions — the search reaches into them), what it is, its product or its
    state, and — folded — by date, renders or rejections. The system's own tests are folded away unless asked for
    ("They are tests, not my work")."""
    from apps.dashboard import board
    from apps.dashboard.views import STATE_ICON, board_cards
    from apps.pipeline.spend_estimates import measured_costs
    listed = history.task_list(_params(request), user=request.user)   # the record's own search and filters
    tasks = [r["task"] for r in listed["rows"]]
    # [his last goal before the pitch, 2026-10-16, Step 1 (4)] every design listed, an old one never folded as a test
    cards = board.classify(tasks, fold_old=False) if tasks else []
    state = request.GET.get("state") or ""
    tests = request.GET.get("tests") == "1"
    folded = sum(1 for c in cards if c.state == board.FOLDED)
    shown = [c for c in cards if (tests or c.state != board.FOLDED) and (not state or c.state == state)]
    pictures = board.pictures(shown)
    rank = {t.pk: i for i, t in enumerate(tasks)}                   # the record's order: newest first, or as asked
    created = {t.pk: t.created_at for t in tasks}
    view = sorted(board_cards(shown, pictures, measured_costs()), key=lambda c: rank[c["task_id"]])
    for c in view:
        c["created"] = created[c["task_id"]]
        c["tag_class"] = TAG_CLASS.get(c["state"], "line")
        c["tag"] = (c["action"] if c["state"] == board.WAITING else
                    STATE_TAGS.get(c["state"]) or (c["fold"] or "").capitalize() or c["action"])
    months, by = [], {}
    for c in view:
        key = created[c["task_id"]].strftime("%B %Y")
        if key not in by:
            by[key] = {"month": key, "tiles": []}
            months.append(by[key])
        by[key]["tiles"].append(c)
    return render(request, "dashboard/history/list.html", dict(
        listed, section="tasks", months=months, shown=len(view), folded=folded, tests=tests, state=state,
        state_filters=STATE_FILTERS, state_icon=STATE_ICON, brands=list(Brand.objects.order_by("id")),
        more_open=any(request.GET.get(k) for k in ("from", "to", "renders", "rejections", "order"))))

# ---- apps/dashboard/views.py :: index (lines 893–901)
@login_required
@ensure_csrf_cookie
def index(request):
    """HOME — THE BOARD (his pick, 2026-09-25). An old address that carried a finished design to start from
    (?from=<output>, the Library's "Start a new design from this one") goes on to the classic start page, where that
    start lives; New design itself is the designer flow (2026-10-27)."""
    if request.GET.get("from"):
        return redirect("%s?from=%s" % (reverse("dashboard:new_classic"), request.GET["from"]))
    return render(request, "dashboard/home.html", board_context(request))

# ---- apps/dashboard/views.py :: library (lines 269–310)
@login_required
@require_GET
def library(request):
    """THE LIBRARY — C's (his pick of the executor's options, a691f56: "starting a design, the library and history are
    C's"): everything a design is made from, on one page — the brand's colours, the faces its type is set in and its
    mark; the materials that can be placed, each artwork once; the granted faces; the products and their sizes; and the
    finished designs with their files — each section a click from its whole page. Read-only; the same library opens
    beside every design while it is worked on (templates/dashboard/_library_panel.html)."""
    from datetime import date

    from apps.dashboard import brand_library as bl
    from apps.dashboard import materials_library as ml
    from apps.dashboard import products as pr
    from apps.ire import brand_mark
    brands = list(Brand.objects.order_by("id"))
    brand = _active_brand(request, brands)
    mark = brand_mark.approved_master()
    try:
        mark_date = date.fromisoformat(str((mark.get("approval") or {}).get("date") or ""))
    except ValueError:
        mark_date = None
    found = ml.search(tier="placeable")
    arts = artworks(found.get("rows") or [])
    faces = [f for f in bl.faces() if f["granted"]]
    stems = {f["stem"]: f for f in faces}
    roles = [dict(r, family=stems[r["face"]]["family"]) for r in bl.type_roles()
             if r["role"] in LIBRARY_ROLES and r.get("face") in stems]
    see = _can_see_finished(request.user)
    finished = _finished_rows() if see else None
    listed = pr.listing(brand)
    products, tests = [r for r in listed if not r["test"]], [r for r in listed if r["test"]]
    return render(request, "dashboard/library/overview.html", {
        "section": "all", "brand": brand, "brands": brands, "colour_systems": bl.colour_systems(brand),
        "mark_approved": mark.get("state") == brand_mark.APPROVED, "mark_date": mark_date,
        "roles": roles, "families": families(faces), "face_count": len(faces),
        "record": found.get("record"), "counts": found.get("counts") or {},
        "counts_words": {k: f"{v:,}" for k, v in (found.get("counts") or {}).items()},
        "artworks": [a for a in arts if a.get("drawable")][:LIBRARY_SAMPLE], "artwork_count": len(arts),
        "products": products[:LIBRARY_SAMPLE], "product_count": len(products), "tests": tests,
        "can_see_finished": see, "finished": [_finished_card(o) for o in finished[:4]] if see else [],
        "finished_count": finished.count() if see else 0,
    })

# ---- apps/dashboard/views.py :: finished_designs (lines 313–347)
@login_required
@require_GET
def finished_designs(request):
    """FINISHED DESIGNS — part of the Library (C's: "one library, with finished designs part of it"): every approved
    design with its own picture and its files, found by words, brand, product category or date; each opens its own
    page. It was a page of its own, outside the one shell, that drew its cards with a script."""
    from urllib.parse import urlencode
    from datetime import date
    see = _can_see_finished(request.user)
    params = {k: (request.GET.get(k) or "").strip()[:100] for k in ("q", "brand", "category", "date_from", "date_to")}
    categories = Product._meta.get_field("category").choices
    if not params["brand"].isdigit():                       # a value the record cannot hold is left out, never a fault
        params["brand"] = ""
    if params["category"] not in dict(categories):
        params["category"] = ""
    for k in ("date_from", "date_to"):
        try:
            date.fromisoformat(params[k])
        except ValueError:
            params[k] = ""
    rows = _finished_rows(params) if see else None
    count = rows.count() if see else 0
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    pages = max(1, -(-count // FINISHED_PAGE))
    page = min(page, pages)
    shown = [_finished_card(o) for o in rows[(page - 1) * FINISHED_PAGE:page * FINISHED_PAGE]] if see else []
    return render(request, "dashboard/library/finished.html", {
        "section": "finished", "can_see_finished": see, "finished": shown, "count": count, "params": params,
        "brands": list(Brand.objects.order_by("name")), "categories": categories,
        "page": page, "pages": pages, "query": urlencode([(k, v) for k, v in params.items() if v]),
        "more_open": any(params[k] for k in ("brand", "category", "date_from", "date_to")),
    }, status=200 if see else 403)

# ---- apps/dashboard/context_processors.py :: round_activity (lines 36–52)
def round_activity(user) -> dict:
    """Only this account's active rounds enter its shell counts and links."""
    from apps.pipeline.models import Round
    groups={key:[] for key in ('run','wait','attn')}
    if user is None or not getattr(user,'is_authenticated',False):
        return groups
    labels={'queued':('run','Queued for the worker'),'running':('run','Working on the round'),
            'awaiting_marks':('wait','Mark up to three inventions'),'awaiting_board_pick':('wait','Pick one mood board'),
            'awaiting_pick':('wait','Pick one candidate'),
            'failed':('attn','Open the failed step')}
    records=Round.objects.filter(created_by=user,state__in=labels).order_by('-updated_at','-pk')
    for record in records:
        key,words=labels[record.state]
        groups[key].append({'title':record.product_brief.get('name','Product round'),
            'url':'/dashboard/rounds/%d/' % record.pk,'reason':record.error_message if record.state=='failed' else '',
            'next_words':words,'picture':None,'round_id':record.pk})
    return groups

# ---- apps/dashboard/board.py :: _executor_test (lines 295–302)
def _executor_test(task) -> bool:
    """[his last goal before the pitch, 2026-10-16, Step 1 (4)] a design the executor started as a test: marked so on
    its own options (``TEST_RUN_OPTION``), or a pitch run of his made before ``PITCH_RUN_TESTS_BEFORE``."""
    options = task.options if isinstance(task.options, dict) else {}
    if options.get(TEST_RUN_OPTION):
        return True
    from apps.pipeline.autopilot import OPTION
    return bool(options.get(OPTION)) and task.created_at is not None and task.created_at < PITCH_RUN_TESTS_BEFORE

# ---- apps/core/tests.py :: DesignAddressTests.test_every_row_of_the_list_is_a_link_to_its_design (lines 1487–1490)
    def test_every_row_of_the_list_is_a_link_to_its_design(self):
        self.client.force_login(self.user)
        html = self.client.get("/dashboard/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        self.assertIn(f'<a class="nm" href="/dashboard/designs/{self.task.pk}/"', html)   # each card of the board

# ---- apps/core/tests.py :: FrontDoorTests.test_each_row_says_where_its_design_stands (lines 1533–1539)
    def test_each_row_says_where_its_design_stands(self):
        from apps.dashboard.words import STATUS_WORDS
        from apps.pipeline.models import TASK_STATUS
        self.assertEqual(set(STATUS_WORDS), {k for k, _ in TASK_STATUS})          # every state has its words
        html = self.client.get("/dashboard/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        self.assertIn(">Choose a concept <svg", html)                                  # each card says it, on the board
        self.assertIn('id="status-words"', self.client.get("/dashboard/new/classic/").content.decode())   # the same map, handed over

# ---- apps/core/tests.py :: HistorySliceTests.test_a_past_design_reads_in_a_designers_words_and_opens_the_live_one (lines 964–994)
    def test_a_past_design_reads_in_a_designers_words_and_opens_the_live_one(self):
        """§BH55 Phase 3: History spoke the engine's — "Task #53", the raw target, the model's own status labels,
        "QA passed", "gate_1 · approve", each reference's stored codes, a notification's kind, a provider operation and
        "tier: PRODUCTION". It says each in the words the rest of the site uses, and every record keeps its own."""
        from apps.pipeline.models import ApiCallRecord, ConceptReference, Notification
        ConceptReference.objects.create(task=self.task, source_type="MATERIAL_LIBRARY", library_item_id="materials:x",
                                        title="a gold pattern", ownership_status="UNKNOWN",
                                        rights_status="UNVERIFIED", image_root="materials", image_path="materials/x.png")
        Notification.objects.create(task=self.task, recipient=self.user, kind="awaiting_gate_2",
                                    message="Design #1: review the design")
        ApiCallRecord.objects.create(task=self.task, provider="openai", model="gpt-image", operation="image:Dusk",
                                     image_count=1, cost_usd="0.25")
        self.client.force_login(self.user)
        html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
        self.assertIn(f"Design #{self.task.pk}", html)
        self.assertNotIn("Task #", html)
        self.assertIn("Product", html)                     # its kind, in the start form's own words
        self.assertIn("Rejected at review", html)                    # its state, in the words the site uses
        self.assertIn("Quality not checked", html)                   # a check that never ran is not a failure
        self.assertIn("The design", html)                            # the decision's gate, in words
        self.assertIn("changes asked for", html)
        self.assertIn("from the materials library", html)            # the reference, in words
        self.assertIn("whose it is: unknown", html)
        self.assertIn("offered — not approved", html)
        self.assertIn("Review the design", html)                     # the notification's kind, in words
        self.assertIn("drew a concept — Dusk", html)                 # what the paid call did
        self.assertIn(f"/dashboard/designs/{self.task.pk}/", html)   # the way to the design itself
        rows = self.client.get("/dashboard/history/").content.decode()
        self.assertIn('<h1 class="h1">Designs</h1>', rows)  # [the owner's answer to the UI directions of 2026-09-25: History is C's Designs]
        self.assertNotIn("Task #", rows)
        self.assertIn("Product", rows)

# ---- apps/core/tests.py :: HistorySliceTests.test_search_reaches_past_the_first_sixty_characters_and_into_the_records (lines 1156–1165)
    def test_search_reaches_past_the_first_sixty_characters_and_into_the_records(self):
        self.client.force_login(self.user)
        for q in ("amethystine", "collar reads copper", "ZZ_UNIQUE_REJECTION_CODE", "Night Oil 52", "TOO_DARK",
                  "Composed the sheet"):
            html = self.client.get("/dashboard/history/", {"q": q}).content.decode()
            self.assertIn(f"/dashboard/history/tasks/{self.task.pk}/", html, q)
        html = self.client.get("/dashboard/history/", {"q": "no-such-thing-52"}).content.decode()
        self.assertNotIn(f"/dashboard/history/tasks/{self.task.pk}/", html)
        html = self.client.get("/dashboard/history/", {"product": str(self.task.product_id), "rejections": "1"}).content.decode()
        self.assertIn(f"/dashboard/history/tasks/{self.task.pk}/", html)

# ---- apps/core/tests.py :: HistorySliceTests.test_designs_are_by_month_each_a_tile_that_opens_the_design_with_its_record_below (lines 1167–1175)
    def test_designs_are_by_month_each_a_tile_that_opens_the_design_with_its_record_below(self):
        self.client.force_login(self.user)
        html = self.client.get("/dashboard/history/").content.decode()
        self.assertIn(self.task.created_at.strftime("%B %Y"), html)                       # its month
        self.assertIn(f'<a class="frame" href="/dashboard/designs/{self.task.pk}/">', html)  # the tile opens the design
        self.assertIn(f'href="/dashboard/history/tasks/{self.task.pk}/">Everything on record</a>', html)
        self.assertIn('<span class="tag ', html)                                          # where it stands, as a tag
        finished = self.client.get("/dashboard/history/", {"state": "finished"}).content.decode()
        self.assertNotIn(f'<a class="frame" href="/dashboard/designs/{self.task.pk}/">', finished)   # by where it stands

# ---- apps/core/tests.py :: HistorySliceTests.test_the_systems_own_tests_are_folded_away_unless_asked_for (lines 1177–1187)
    def test_the_systems_own_tests_are_folded_away_unless_asked_for(self):
        # his fold (a691f56): "They are tests, not my work"
        from apps.dashboard import board
        self.client.force_login(self.user)
        with patch.dict(board.OWNER_FOLD, {self.task.pk: "demo carton"}, clear=True):
            folded = self.client.get("/dashboard/history/").content.decode()
            asked = self.client.get("/dashboard/history/", {"tests": "1"}).content.decode()
        tile = f'<a class="frame" href="/dashboard/designs/{self.task.pk}/">'
        self.assertNotIn(tile, folded)
        self.assertIn("Show the system's own tests (1)", folded)
        self.assertIn(tile, asked)

# ---- apps/core/tests.py :: LibraryPageTests.test_the_library_is_everything_a_design_is_made_from_on_one_page (lines 1926–1938)
    def test_the_library_is_everything_a_design_is_made_from_on_one_page(self):
        html = self.client.get("/dashboard/library/").content.decode()
        self.assertIn('<h1 class="h1">Library</h1>', html)
        for part in ("colours", "faces", "mark", "materials", "all-faces", "products", "finished"):
            self.assertIn(f'id="{part}"', html, part)
        self.assertIn("Amethyst Rose", html)                                          # a colour, by its name
        self.assertIn("#8B3A52", html)
        self.assertIn("35 × 35 × 100 mm", html)                                     # a product, by its size
        self.assertIn(f'href="/dashboard/library/finished/{self.output.pk}/"', html)   # a finished design, its page
        self.assertIn('aria-current="page">All</a>', html)
        self.assertIn('href="/dashboard/library/finished/">Finished designs</a>', html)
        self.assertIn('href="/dashboard/library/"', self.client.get("/dashboard/").content.decode())   # the bar's Library
        self.assertNotIn("product_container", html)

# ---- apps/core/tests.py :: LibraryPageTests.test_finished_designs_are_found_by_words_brand_category_and_date (lines 1964–1977)
    def test_finished_designs_are_found_by_words_brand_category_and_date(self):
        found = self.client.get("/dashboard/library/finished/", {"q": "night oil"}).content.decode()
        self.assertIn(f'href="/dashboard/library/finished/{self.output.pk}/"', found)
        none = self.client.get("/dashboard/library/finished/", {"q": "zzzz"}).content.decode()
        self.assertNotIn(f'href="/dashboard/library/finished/{self.output.pk}/"', none)
        self.assertIn("No finished design matches", none)
        self.assertIn(f'href="/dashboard/library/finished/{self.output.pk}/"', self.client.get(
            "/dashboard/library/finished/", {"brand": self.brand.pk, "category": "CO"}).content.decode())
        later = self.client.get("/dashboard/library/finished/", {"date_from": "2999-01-01"}).content.decode()
        self.assertNotIn(f'href="/dashboard/library/finished/{self.output.pk}/"', later)
        for bad in ({"brand": "x"}, {"category": "ZZ"}, {"date_from": "not a date"}, {"page": "x"}):
            res = self.client.get("/dashboard/library/finished/", bad)                # left out, never a fault
            self.assertEqual(res.status_code, 200, bad)
            self.assertIn(f'href="/dashboard/library/finished/{self.output.pk}/"', res.content.decode(), bad)

# ---- apps/pipeline/tests/test_product_round_page.py :: test_shell_and_pulse_include_only_owned_active_rounds (lines 255–271)
def test_shell_and_pulse_include_only_owned_active_rounds(client,owner,isolated,monkeypatch):
    from apps.dashboard import board,context_processors
    other=get_user_model().objects.create_user(username='foreign-round-shell')
    for state in ('awaiting_marks','awaiting_pick','queued','running','failed','complete'):
        Round.objects.create(slug='own-'+state,request_key=str(uuid4()),created_by=owner,
                             product_brief={'name':'Own '+state},state=state)
        Round.objects.create(slug='foreign-'+state,request_key=str(uuid4()),created_by=other,
                             product_brief={'name':'Foreign '+state},state=state)
    pills=context_processors.pills(cards=[],user=owner)
    assert {p['key']:p['count'] for p in pills}=={'run':2,'wait':2,'attn':1}
    assert all(c['title'].startswith('Own ') for p in pills for c in p['cards'])
    monkeypatch.setattr(board,'counts',lambda:{board.WORKING:3,board.WAITING:4,board.ATTENTION:5})
    pulse=client.get(reverse('dashboard:pulse')).json()
    assert pulse['counts']=={'run':5,'wait':6,'attn':6}
    response=client.get(reverse('dashboard:round_list'))
    assert b'>Rounds</a>' in response.content
    assert b'Your rounds' in response.content

# ---- apps/pipeline/tests/test_browser_review_board_references.py :: DesignAddressBrowserTests.test_opening_a_design_moves_the_address_and_back_returns (lines 278–294)
    def test_opening_a_design_moves_the_address_and_back_returns(self):
        # [the owner's answer to the UI directions of 2026-09-25: a design is opened from the board, each card a link to
        # the design's own page; back returns to the board]
        first, second = self._task("the first carton"), self._task("the second carton")
        page = self._page()
        page.goto(self.live_server_url + "/dashboard/", wait_until="domcontentloaded")
        page.click(f'a.nm[href="/dashboard/designs/{first.id}/"]')
        page.wait_for_function(f"location.pathname === '/dashboard/designs/{first.id}/'")
        self._titled(page, "the first")
        page.go_back()
        page.wait_for_function("location.pathname === '/dashboard/'")
        page.click(f'a.nm[href="/dashboard/designs/{second.id}/"]')
        page.wait_for_function(f"location.pathname === '/dashboard/designs/{second.id}/'")
        self._titled(page, "the second")
        page.go_back()
        page.wait_for_function("location.pathname === '/dashboard/'")
        assert page.is_visible("h1:text-is('Board')")

# ---- apps/pipeline/tests/test_browser_review_board_references.py :: DesignAddressBrowserTests.test_the_board_fits_a_phones_width (lines 309–322)
    def test_the_board_fits_a_phones_width(self):
        # [the owner's answer to the UI directions of 2026-09-25: the home is the board — at a phone's width the three
        # counts wrap and a long product name never pushes the filter past the edge]
        from apps.core.models import Product
        product = Product.objects.create(brand=Brand.objects.first(), product_id="BBR-PH-1", category="CO", year=2026,
                                         name="Rose Damascena Night Repair Oil with a Name Longer Than a Phone")
        DesignTask.objects.create(brand=Brand.objects.first(), product=product, task_text="a long-named carton",
                                  design_target="packaging", status="awaiting_gate_1", created_by=self.user)
        ctx = self._context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto(self.live_server_url + "/dashboard/", wait_until="domcontentloaded")
        assert page.is_visible("#board-product")
        assert page.evaluate("document.documentElement.scrollWidth <= "
                             "document.documentElement.clientWidth") is True

# ---- apps/pipeline/tests/test_browser_review_board_references.py :: DesignAddressBrowserTests.test_the_library_opens_a_finished_design_and_starts_a_new_one_from_it (lines 395–416)
    def test_the_library_opens_a_finished_design_and_starts_a_new_one_from_it(self):
        # §BH55 Phase 3 p3-library: a finished design's way back to itself, and a new design started from it, filled in
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        task = self._task("A carton for the night oil")
        concept = GeneratedImage.objects.create(task=task, direction_name="Nocturne", prompt_used="p")
        PackagingOutput.objects.create(task=task, approved_image=concept, spec_sheet={}, is_final_approved=True)
        page = self._page()
        page.goto(self.live_server_url + "/dashboard/library/", wait_until="domcontentloaded")
        page.click(".card.fin a.frame")                     # [the owner's answer to the UI directions of 2026-09-25: the Library is C's — one page, finished designs part of it]: a finished design's own page
        page.click("text=Open the design")
        page.wait_for_function(f"location.pathname === '/dashboard/designs/{task.id}/'")
        self._titled(page, "A carton for the night oil")
        page.goto(self.live_server_url + "/dashboard/library/", wait_until="domcontentloaded")
        page.click(".card.fin a.frame")
        page.wait_for_selector("text=Open the design")
        # [the designer flow of 2026-10-27] the start from a finished design is a classic path: unlinked, kept in the code
        assert page.locator("text=Start a new design from this one").count() == 0
        output = PackagingOutput.objects.get(task=task)
        page.goto(self.live_server_url + f"/dashboard/new/classic/?from={output.pk}", wait_until="domcontentloaded")
        page.wait_for_selector("#start-from")
        assert page.input_value("#task-input") == "A carton for the night oil"
        assert page.get_attribute('.target-chip[data-target="packaging"]', "aria-checked") == "true"
