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
    # Ingredients
    path("ingredients/", views.ingredient_list, name="admin-ingredient-list"),
    path("ingredients/<slug:slug>/", views.ingredient_detail, name="admin-ingredient-detail"),
    path("ingredients/<slug:slug>/update/", views.ingredient_update, name="admin-ingredient-update"),
    # Community Submissions
    path("submissions/", views.submission_list, name="admin-submission-list"),
    path("submissions/<uuid:submission_id>/", views.submission_detail, name="admin-submission-detail"),
    path("submissions/<uuid:submission_id>/review/", views.submission_review, name="admin-submission-review"),
    # Dataset Releases
    path("releases/", views.release_list, name="admin-release-list"),
    path("releases/create/", views.release_create, name="admin-release-create"),
    # ChangeLog
    path("changelog/", views.changelog_list, name="admin-changelog-list"),
    # QA Observatory
    path("zero-results/", views.zero_results_list, name="admin-zero-results"),
    # Cache
    path("cache/clear/", views.cache_clear, name="admin-cache-clear"),
]
