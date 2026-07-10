from flask import Blueprint

material_bp = Blueprint(
    "material",
    __name__
)


@material_bp.route("/material")
def material():

    return "<h1>Material Module</h1>"