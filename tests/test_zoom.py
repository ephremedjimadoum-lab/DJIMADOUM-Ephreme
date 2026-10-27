import pytest

from agent_compte_rendu.zoom import _attendre_la_fin, _rejoindre, analyser_lien


def test_analyser_lien_invitation():
    r = analyser_lien("https://us02web.zoom.us/j/85512345678?pwd=AbC123.1")
    assert (r.numero, r.code) == ("85512345678", "AbC123.1")
    assert r.url_client_web("Robot").startswith("https://app.zoom.us/wc/join/85512345678?prefer=1&un=")
    assert r.url_client_web("Robot").endswith("&pwd=AbC123.1")


def test_analyser_numero_seul():
    r = analyser_lien("855 1234 5678", code="9999")
    assert (r.numero, r.code) == ("85512345678", "9999")


def test_lien_invalide():
    with pytest.raises(ValueError):
        analyser_lien("https://exemple.com/j/85512345678")


# Page qui reproduit les éléments du client web Zoom utilisés par le robot.
FAUSSE_PAGE_ZOOM = """<!doctype html><html><body>
<div id="preview">
  <input id="input-for-name">
  <button id="preview-audio-control-button" aria-label="Mute" onclick="this.setAttribute('aria-label','Unmute')">mic</button>
  <button id="preview-video-control-button" aria-label="Stop Video" onclick="this.setAttribute('aria-label','Start Video')">cam</button>
  <button class="preview-join-button" onclick="rejoindre()">Join</button>
</div>
<div id="etat"></div>
<script>
function rejoindre() {
  window.nom = document.getElementById('input-for-name').value;
  window.micro = document.getElementById('preview-audio-control-button').getAttribute('aria-label');
  window.camera = document.getElementById('preview-video-control-button').getAttribute('aria-label');
  document.getElementById('preview').remove();
  document.getElementById('etat').textContent = 'Please wait, the meeting host will let you in soon.';
  setTimeout(() => {
    document.getElementById('etat').innerHTML =
      '<button onclick="window.audio=1">Join Audio by Computer</button><button>Leave</button>';
  }, 1500);
  setTimeout(() => {
    document.getElementById('etat').textContent = 'This meeting has been ended by host';
  }, 9000);
}
</script></body></html>"""


def test_parcours_robot_sur_fausse_page_zoom():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            navigateur = p.chromium.launch()
        except Exception as erreur:
            pytest.skip(f"Chromium indisponible : {erreur}")
        page = navigateur.new_page()
        page.route("https://app.zoom.us/**", lambda route: route.fulfill(content_type="text/html", body=FAUSSE_PAGE_ZOOM))

        _rejoindre(page, analyser_lien("https://zoom.us/j/85512345678?pwd=x"), "Assistant CR", attente_max_s=30)
        assert page.evaluate("[window.nom, window.micro, window.camera, window.audio]") == [
            "Assistant CR", "Unmute", "Start Video", 1,
        ]

        _attendre_la_fin(page, duree_max_s=30)
        assert "ended by host" in page.inner_text("body")
        navigateur.close()
