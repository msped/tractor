from django_components import component, register


@register("navbar")
class Navbar(component.Component):
    template_name = "navbar/template.html"

    def get_context_data(self, user):
        return {
            'user': user
        }
