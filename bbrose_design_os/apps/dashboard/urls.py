from django.urls import path
from . import product_round_views, round_files_views

from . import history_views, loop_views, regeneration_views, views

app_name = "dashboard"

urlpatterns = [
    path('rounds/', product_round_views.index, name='round_list'),
    path('rounds/new/', product_round_views.new, name='round_new'),
    path('rounds/new/stand/', product_round_views.stand_preview, name='round_new_stand'),
    path('rounds/<int:pk>/', product_round_views.detail, name='product_round'),
    path('rounds/<int:pk>/pick/', product_round_views.pick, name='product_round_pick'),
    path('rounds/<int:pk>/board/', product_round_views.board, name='product_round_board'),
    path('rounds/<int:pk>/research/', product_round_views.research, name='product_round_research'),
    path('rounds/<int:pk>/none-of-these/', product_round_views.none_of_these, name='product_round_none'),
    path('rounds/<int:pk>/retry/', product_round_views.retry, name='product_round_retry'),
    path('rounds/<int:pk>/files/<path:relative>', product_round_views.artifact, name='product_round_file'),
    path('rounds/<int:pk>/build-files/', round_files_views.start, name='product_round_files_start'),
    path('rounds/<int:pk>/built-files/', round_files_views.detail, name='product_round_files'),
    path('rounds/<int:pk>/built-files/retry/', round_files_views.retry, name='product_round_files_retry'),
    path('rounds/<int:pk>/built-files/face/<slug:key>/accept/', round_files_views.accept_face, name='product_round_files_accept'),
    path('rounds/<int:pk>/built-files/accept-all/', round_files_views.accept_all, name='product_round_files_accept_all'),
    path('rounds/<int:pk>/built-files/face/<slug:key>/redraw/', round_files_views.redraw_face, name='product_round_files_redraw'),
    path('rounds/<int:pk>/built-files/make/', round_files_views.make_files, name='product_round_files_make'),
    path('rounds/<int:pk>/built-files/download/<path:relative>', round_files_views.artifact, name='product_round_files_download'),
    path("", views.index, name="index"),
    # the owner's designer flow of 2026-10-27: New design starts research, three mood boards, three designs, a pick
    path("new/", product_round_views.new, name="new"),
    # the start page of 2026-09-25 (display, carton, palette, complete product), kept in the code and unlinked
    path("new/classic/", views.new_design, name="new_classic"),
    # the top bar's three counts, refreshed while a page stays open, and the house mark it draws
    path("pulse/", views.pulse, name="pulse"),
    path("find/", views.find, name="find"),
    path("brand/mark.svg", views.brand_mark_svg, name="brand_mark_svg"),
    # §BH55 Phase 3: ONE DESIGN'S OWN ADDRESS — the dashboard opened on that design
    path("designs/<int:task_id>/", views.design, name="design"),
    # [his last goal before the pitch, 2026-10-16, Step 1 (6)] its Adjust panel's controls, fetched after the page shows
    path("designs/<int:task_id>/adjust/", views.design_adjust, name="design_adjust"),
    path("designs/<int:task_id>/concepts/<int:image_id>.jpg", views.concept_thumb, name="concept_thumb"),
    # the owner's answer to the UI directions of 2026-09-25: the Library is C's — everything a design is made from on
    # one page, the finished designs part of it (their list and each one's own page; they were a page of their own)
    path("library/", views.library, name="library"),
    path("library/finished/", views.finished_designs, name="finished_designs"),
    path("library/finished/<int:output_id>/", views.finished_design, name="finished_design"),
    # §BH55 Phase 3: the brand's own library — what designs are made from, read-only
    path("brand/", views.brand_library, name="brand_library"),
    path("brand/faces/<str:stem>.png", views.face_specimen, name="face_specimen"),
    path("brand/mark.png", views.brand_mark, name="brand_mark"),
    path("brand/references/", views.house_references, name="house_references"),
    # §BH55 Phase 3: the governed materials — read from the tier record and the caption record, never the brain
    path("materials/", views.materials_library, name="materials_library"),
    path("materials/pictures/<int:n>-<slug:sha>.png", views.material_picture, name="material_picture"),
    # Day 7 §5: the library index — a file's detail and its hash-named preview
    path("materials/previews/<slug:sha>.png", views.material_preview, name="material_preview"),
    path("materials/<slug:sha>/", views.material_detail, name="material_detail"),
    # §BH55 Phase 3: the products and their sizes — a designer sets a size here
    path("products/", views.products_library, name="products_library"),
    # §BH55 Phase 3: the status of the system — slice 4 of §BH51
    path("status/", views.status_page, name="status"),
    # §BH55 Phase 3: the owner's register of rulings and his review queue, read on the site
    path("status/rulings/", views.rulings_page, name="rulings"),
    path("status/rulings/<slug:source>/<int:line>/", views.ruling_detail, name="ruling"),
    path("products/<int:pk>/size/", views.product_size, name="product_size"),
    # §BH52(b) slice 1 — HISTORY: every past task, read-only, from its rows
    path("history/", history_views.history_index, name="history"),
    path("history/tasks/<int:task_id>/", history_views.history_task, name="history_task"),
    path("history/projects/", history_views.history_projects, name="history_projects"),
    path("history/projects/<int:project_id>/", history_views.history_project, name="history_project"),
    path("history/dieline-jobs/", history_views.history_dieline_jobs, name="history_dieline_jobs"),
    path("history/concepts/", history_views.history_concepts, name="history_concepts"),
    # §BH52(b): (a)'s explorations, labelled, never among outputs
    path("history/explorations/", history_views.history_explorations, name="history_explorations"),
    path("history/explorations/<slug:study>/", history_views.history_exploration_study,
         name="history_exploration_study"),
    path("history/explorations/<slug:study>/<slug:picture>.png", history_views.history_exploration_picture,
         name="history_exploration_picture"),
    # §BH54(k) slice 2 — the design loop: an exploration render of a task, the owner's alone, at no gate cost
    path("history/tasks/<int:task_id>/explore/", loop_views.exploration_render_view, name="history_task_explore"),
    path("history/tasks/<int:task_id>/loop/", loop_views.exploration_loop_view, name="history_task_loop"),
    # §BH54(b) (k) 3: accept or reject by eye — the owner's act alone, with his identity, the time and the sha256
    path("history/tasks/<int:task_id>/accept/", loop_views.exploration_accept_view, name="history_task_accept"),
    # §BH54(b) (k) 4: the copy channel — the six pieces typed into the product, each piece's room measured as he types
    path("history/tasks/<int:task_id>/copy/", loop_views.copy_save_view, name="history_task_copy"),
    path("history/tasks/<int:task_id>/copy-room/", loop_views.copy_room_view, name="history_task_copy_room"),
    # §BH55 Phase 1: his acceptance of a governed design — the owner's act alone, with his identity, the time and the hash
    path("history/tasks/<int:task_id>/accept-design/", loop_views.design_accept_view, name="history_task_accept_design"),
    # PALT-M4C M4C-4: the owner confirmation surface for palette design
    # intent. Committed files are not a review boundary - the dashboard
    # has to serve it.
    path("palette/intent-confirmation/", views.palette_intent_confirmation,
         name="palette_intent_confirmation"),
    # PALT-M4C-4 §2: the governed, task-scoped confirmation. The bare route
    # above stays a read-only preview — a confirmation needs something to
    # be recorded against.
    path("palette/intent-confirmation/<int:task_id>/",
         views.palette_intent_confirmation,
         name="palette_intent_confirmation_task"),
    # 2A-6E-CORR-4: browser-independent Gate-1 regeneration — the essential
    # workflow is server-rendered HTML and works with JavaScript disabled.
    path("tasks/<int:task_id>/gate1-regeneration/confirm/",
         regeneration_views.gate1_regeneration_confirm,
         name="gate1_regeneration_confirm"),
    path("tasks/<int:task_id>/gate1-regeneration/jobs/<int:job_id>/",
         regeneration_views.gate1_regeneration_status,
         name="gate1_regeneration_status"),
]
