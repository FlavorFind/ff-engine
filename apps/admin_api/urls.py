"""
URL configuration for the Engine Admin API.
Mounted at /v1/admin/ in config/urls.py.
All endpoints require the internal:admin scope.
"""

from django.urls import path

from . import views

urlpatterns = [
    # API Clients
    path("clients/", views.client_list, name="admin-client-list"),
    path("clients/create/", views.client_create, name="admin-client-create"),
    path("clients/<uuid:client_id>/", views.client_detail, name="admin-client-detail"),
    path("clients/<uuid:client_id>/update/", views.client_update, name="admin-client-update"),
    path("clients/<uuid:client_id>/keys/", views.client_generate_key, name="admin-client-generate-key"),
    # API Keys
    path("keys/<uuid:key_id>/revoke/", views.key_revoke, name="admin-key-revoke"),
    # Usage
    path("usage/", views.usage_list, name="admin-usage-list"),
    path("usage/<uuid:client_id>/", views.usage_client, name="admin-usage-client"),
    # Dishes
    path("dishes/", views.dish_list, name="admin-dish-list"),
    path("dishes/<slug:slug>/", views.dish_detail, name="admin-dish-detail"),
    path("dishes/<slug:slug>/update/", views.dish_update, name="admin-dish-update"),
    path("dishes/<slug:slug>/promote/", views.dish_promote, name="admin-dish-promote"),
    path("dishes/<slug:slug>/changelog/", views.dish_changelog, name="admin-dish-changelog"),
    path("dishes/<slug:slug>/aliases/", views.dish_aliases, name="admin-dish-aliases"),
    path("dishes/<slug:slug>/aliases/add/", views.dish_alias_add, name="admin-dish-alias-add"),
    path("dishes/<slug:slug>/dietary-tags/", views.dish_dietary_tags, name="admin-dish-dietary-tags"),
    path("dishes/<slug:slug>/dietary-tags/set/", views.dish_dietary_tag_set, name="admin-dish-dietary-tag-set"),
    path("dishes/<slug:slug>/dietary-tags/remove/", views.dish_dietary_tag_remove, name="admin-dish-dietary-tag-remove"),
    path("dishes/<slug:slug>/dietary-tags/rederive/", views.dish_dietary_rederive, name="admin-dish-dietary-rederive"),
    # Dish Aliases (delete by alias ID)
    path("dish-aliases/<int:alias_id>/delete/", views.dish_alias_delete, name="admin-dish-alias-delete"),
    # Ingredients
    path("ingredients/", views.ingredient_list, name="admin-ingredient-list"),
    path("ingredients/<slug:slug>/", views.ingredient_detail, name="admin-ingredient-detail"),
    path("ingredients/<slug:slug>/update/", views.ingredient_update, name="admin-ingredient-update"),
    path("ingredients/<slug:slug>/nutrition/", views.nutrition_ingredient, name="admin-ingredient-nutrition"),
    path("ingredients/<slug:slug>/nutrition/delete/", views.nutrition_delete, name="admin-ingredient-nutrition-delete"),
    # Ingredient Categories
    path("ingredient-categories/", views.ingredient_category_list, name="admin-ingredient-categories"),
    # Community Submissions
    path("submissions/", views.submission_list, name="admin-submission-list"),
    path("submissions/<uuid:submission_id>/", views.submission_detail, name="admin-submission-detail"),
    path("submissions/<uuid:submission_id>/review/", views.submission_review, name="admin-submission-review"),
    # Dataset Releases
    path("releases/", views.release_list, name="admin-release-list"),
    path("releases/create/", views.release_create, name="admin-release-create"),
    # ChangeLog
    path("changelog/", views.changelog_list, name="admin-changelog-list"),
    # Regions
    path("regions/", views.region_list_admin, name="admin-region-list"),
    path("regions/create/", views.region_create, name="admin-region-create"),
    path("regions/<slug:slug>/", views.region_detail_admin, name="admin-region-detail"),
    path("regions/<slug:slug>/update/", views.region_update, name="admin-region-update"),
    path("regions/<slug:slug>/assign-dish/", views.region_assign_dish, name="admin-region-assign-dish"),
    path("regions/<slug:slug>/remove-dish/", views.region_remove_dish, name="admin-region-remove-dish"),
    # Dietary Tags
    path("dietary-tags/", views.dietary_tag_list, name="admin-dietary-tag-list"),
    path("dietary-tags/create/", views.dietary_tag_create, name="admin-dietary-tag-create"),
    # Pairings
    path("pairings/", views.pairing_list, name="admin-pairing-list"),
    path("pairings/create/", views.pairing_create, name="admin-pairing-create"),
    path("pairings/<int:pairing_id>/update/", views.pairing_update, name="admin-pairing-update"),
    path("pairings/<int:pairing_id>/delete/", views.pairing_delete, name="admin-pairing-delete"),
    # Substitutions
    path("substitutions/", views.substitution_list, name="admin-substitution-list"),
    path("substitutions/create/", views.substitution_create, name="admin-substitution-create"),
    path("substitutions/<int:sub_id>/update/", views.substitution_update, name="admin-substitution-update"),
    path("substitutions/<int:sub_id>/delete/", views.substitution_delete, name="admin-substitution-delete"),
    # Nutrition Facts
    path("nutrition/", views.nutrition_list, name="admin-nutrition-list"),
    # Sources
    path("sources/", views.source_list, name="admin-source-list"),
    path("sources/create/", views.source_create, name="admin-source-create"),
    path("sources/<int:source_id>/update/", views.source_update, name="admin-source-update"),
    path("sources/<int:source_id>/delete/", views.source_delete, name="admin-source-delete"),
    # QA Observatory
    path("zero-results/", views.zero_results_list, name="admin-zero-results"),
    path("qa-report/", views.qa_report, name="admin-qa-report"),
    path("duplicate-check/", views.duplicate_check, name="admin-duplicate-check"),
    # Cache
    path("cache/clear/", views.cache_clear, name="admin-cache-clear"),
    path("cache/warm/", views.cache_warm, name="admin-cache-warm"),
    # CSV Export
    path("export/", views.csv_export, name="admin-csv-export"),
]
