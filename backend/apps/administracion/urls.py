from django.urls import path

from .views.rbac_views import (
    AssignRolePermissionsView,
    EmpleadoSermedLookupView,
    PermissionsCatalogView,
    RevokeRolePermissionView,
    RoleDetailView,
    RolesListCreateView,
    UserActivateView,
    UserCdLaboralesView,
    UserDeactivateView,
    UserDetailView,
    UserExportView,
    UserOverrideRemoveView,
    UserOverridesView,
    UserPrimaryRoleView,
    UserResetPasswordView,
    UserRoleRevokeView,
    UserRolesView,
    UsersListCreateView,
    UsersNotifyView,
)

from .views.expediente_view import ExpedienteView, ActualizarExpedienteView, BuscarPorNombreView
from .views.user_import_views import (
    UserImportConfirmView,
    UserImportPreviewView,
    UserImportTemplateView,
)
from .views.navigation_menu_views import ModuleCatalogView, NavigationMenuView
from .views.clinicas_views import ClinicasListView
from .views.navigation_module_mutation_views import (
    CreateModuleView,
    ModuleVisibilityView,
    ReorderModulesView,
    UpdateModuleView,
)


def _modules_collection_view(request, *args, **kwargs):
    """
    `GET /modules` (catalogo, `ModuleCatalogView`) y `POST /modules`
    (alta, `CreateModuleView`) comparten la misma ruta -- mismo patron REST
    que `RolesListCreateView`/`UsersListCreateView`, pero acá cada verbo
    vive en su propia clase (lectura en `navigation_menu_views.py`,
    escritura en `navigation_module_mutation_views.py`) para no mezclar
    las dependencias de un endpoint de solo-lectura con las de un
    endpoint de escritura con CSRF/policy de mutacion. Django no permite
    dos `path()` con el mismo string apuntando a vistas distintas -- este
    despachador por metodo HTTP es el punto de union.
    """
    if request.method == "POST":
        return CreateModuleView.as_view()(request, *args, **kwargs)
    return ModuleCatalogView.as_view()(request, *args, **kwargs)


urlpatterns = [
    path("navigation-menu", NavigationMenuView.as_view(), name="navigation-menu"),
    path("clinicas", ClinicasListView.as_view(), name="clinicas-list"),
    path("modules", _modules_collection_view, name="module-catalog"),
    path("modules/reorder", ReorderModulesView.as_view(), name="module-reorder"),
    path("modules/<str:clave>", UpdateModuleView.as_view(), name="module-update"),
    path(
        "modules/<str:clave>/visibility",
        ModuleVisibilityView.as_view(),
        name="module-visibility",
    ),
    path("roles", RolesListCreateView.as_view(), name="rbac-roles-list-create"),
    path("roles/<int:role_id>", RoleDetailView.as_view(), name="rbac-role-detail"),
    path("permissions", PermissionsCatalogView.as_view(), name="rbac-permissions-list"),
    path("permissions/assign", AssignRolePermissionsView.as_view(), name="rbac-role-permissions-assign"),
    path(
        "permissions/roles/<int:role_id>/permissions/<int:permission_id>",
        RevokeRolePermissionView.as_view(),
        name="rbac-role-permission-revoke",
    ),
    path("users", UsersListCreateView.as_view(), name="rbac-users-list-create"),
    path("users/import/template", UserImportTemplateView.as_view(), name="rbac-users-import-template"),
    path("users/import/preview", UserImportPreviewView.as_view(), name="rbac-users-import-preview"),
    path("users/import/confirm", UserImportConfirmView.as_view(), name="rbac-users-import-confirm"),
    path("users/<int:user_id>", UserDetailView.as_view(), name="rbac-user-detail-update"),
    path("users/<int:user_id>/activate", UserActivateView.as_view(), name="rbac-user-activate"),
    path("users/<int:user_id>/deactivate", UserDeactivateView.as_view(), name="rbac-user-deactivate"),
    path("users/<int:user_id>/reset-password", UserResetPasswordView.as_view(), name="rbac-user-reset-password"),
    path("users/<int:user_id>/roles", UserRolesView.as_view(), name="rbac-user-roles-assign"),
    path("users/<int:user_id>/roles/primary", UserPrimaryRoleView.as_view(), name="rbac-user-role-primary"),
    path("users/<int:user_id>/roles/<int:role_id>", UserRoleRevokeView.as_view(), name="rbac-user-role-revoke"),
    path("users/<int:user_id>/overrides", UserOverridesView.as_view(), name="rbac-user-overrides-upsert"),
    path("users/<int:user_id>/overrides/<str:code>", UserOverrideRemoveView.as_view(), name="rbac-user-override-remove"),
    path('expedientes/', ExpedienteView.as_view(), name='buscar'),
    path('expedientes/actualizar/', ActualizarExpedienteView.as_view(), name='actualizar'),
    path('expedientes/buscar-nombre/', BuscarPorNombreView.as_view(), name='buscar-nombre'),
    path('users/empleados-sermed/<str:no_exp>', EmpleadoSermedLookupView.as_view(), name='rbac-empleado-sermed-lookup'),
    path("users/notify", UsersNotifyView.as_view(), name="rbac-users-notify"),
    path("users/export", UserExportView.as_view(), name="rbac-users-export"),
    path("users/cd-laborales", UserCdLaboralesView.as_view(), name="rbac-users-cd-laborales"),
]
