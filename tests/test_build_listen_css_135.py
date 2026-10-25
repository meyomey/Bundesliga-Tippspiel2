"""(135) Deliverable-Waechter: die Seiten-CSS muessen in den GitHub-Upload.

quick_tip.css / tip_overview.css / admin_bots.css standen bis 3.1.104 nur im
Runtime-Zip - frische Repository-Clones hatten ungestylte Schnelltipp- und
Uebersichts-Seiten (der /schnelltipp-Smoke-Test prueft nur den Link-Tag,
nicht die Datei).
"""


def test_seiten_css_in_github_upload_liste_135():
    t = open("build_lieferungen.py", encoding="utf-8").read()
    for datei in ("static/css/quick_tip.css",
                  "static/css/tip_overview.css",
                  "static/css/admin_bots.css"):
        assert '"%s"' % datei in t, "fehlt in GITHUB_UPLOAD_FILES: " + datei
