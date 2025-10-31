from django_components import component


class Navbar(component.Component):
    template_name = "navbar/template.html"

    def get_context_data(self, request):
        return {
            'user': request.user
        }
