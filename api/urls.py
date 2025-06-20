from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, LogoutView, DocumentViewSet

# Create a router and register our viewsets with it.
# DefaultRouter automatically creates the URL patterns for standard actions (list, create, retrieve, update, destroy)
# and also for custom @action decorated methods in the ViewSet.
router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
# The 'basename' is used to generate URL names. If your ViewSet has a 'queryset' attribute,
# DRF can often infer it, but it's good practice to set it, especially for clarity or complex cases.
# For DocumentViewSet, 'basename' will prefix URL names like 'document-list', 'document-detail', 'document-ask-ai'.

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('', include(router.urls)), # Include all URLs generated by the router
                                    # This will make '/api/documents/' and '/api/documents/{pk}/' etc., available.
                                    # The custom 'ask-ai' action will be at '/api/documents/{pk}/ask-ai/'
]