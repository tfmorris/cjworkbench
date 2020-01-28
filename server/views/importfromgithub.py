from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from rest_framework import status
from rest_framework.decorators import api_view
from cjwstate.importmodule import WorkbenchModuleImportError, import_module_from_url
from server.serializers import JsonizeContext, jsonize_clientside_module
from cjworkbench.i18n.trans import MESSAGE_LOCALIZER_REGISTRY


@api_view(["POST"])
@login_required
def import_from_github(request):
    if not request.user.is_staff:
        return JsonResponse(
            {"error": "Only an admin can call this method"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        clientside_module = import_module_from_url(request.data["url"])
        MESSAGE_LOCALIZER_REGISTRY.update_supported_modules()
        ctx = JsonizeContext(request.user, request.session, request.locale_id)
        data = jsonize_clientside_module(clientside_module, ctx)
        return JsonResponse(data, status=status.HTTP_201_CREATED)
    except WorkbenchModuleImportError as err:
        # Respond with 200 OK so the client side can read the error message.
        # TODO make the client smarter
        return JsonResponse({"error": str(err)}, status=status.HTTP_200_OK)
