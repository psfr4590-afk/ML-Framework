"""Model Lab release-contract tests that do not require a GUI or live services."""
from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT
EXPECTED_NAV=["Dashboard","Datasets","Pipeline","Credentials","Sources","Crawler","Training","Outputs","Logs","System","Configuration","Diagnostics","Command Center"]
EXPECTED_STAGES=["crawl","clean","dedup","weight","tokenize","shard","train","export"]
EXPECTED_CREDS={"github":("GitHub","GITHUB_TOKEN"),"huggingface":("Hugging Face","HF_TOKEN"),"google_api":("Google","GOOGLE_API_KEY"),"google_cx":("Google","GOOGLE_CX")}
SCREEN_FILES={"Dashboard":"dashboard.py","Datasets":"dataset.py","Pipeline":"pipeline.py","Credentials":"credentials.py","Sources":"sources.py","Crawler":"crawler.py","Training":"training.py","Outputs":"outputs.py","Logs":"logs.py","System":"system.py","Configuration":"configuration.py","Diagnostics":"diagnostics.py","Command Center":"command_center.py"}
def text(path): return path.read_text(encoding="utf-8")
def test_package_identity_is_model_lab():
 readme=text(ROOT/"README.md"); assert "Model Lab" in readme and "M²S Model Training Pipeline" in readme
def test_root_launcher_exists_and_uses_project_root():
 p=ROOT/"launch.py"; assert p.exists(); tree=ast.parse(text(p)); assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="main" for n in ast.walk(tree)); assert "resolve().parent" in text(p)
def test_navigation_contract_has_all_required_surfaces():
 src=text(ROOT/"ui/core/navigation.py")
 for item in EXPECTED_NAV: assert item in src
def test_all_navigation_screen_modules_exist():
 for name,filename in SCREEN_FILES.items(): assert (ROOT/"ui/screens"/filename).exists(),name
def test_navigation_factories_cover_all_items():
 src=text(ROOT/"ui/core/application.py")
 for name,filename in SCREEN_FILES.items(): assert filename[:-3] in src,f"missing screen import: {name}"
 nav=text(ROOT/"ui/core/navigation.py"); assert '("Datasets","Dataset")' in nav
 for key in ["Dashboard","System","Credentials","Sources","Crawler","Dataset","Pipeline","Training","CommandCenter","Outputs","Logs","Configuration","Diagnostics"]: assert f'"{key}":' in src
def test_pipeline_stage_contract_is_complete():
 src=text(ROOT/"ui/core/config.py")
 for stage in EXPECTED_STAGES: assert f'"{stage}"' in src
def test_pipeline_service_rejects_unknown_stage():
 assert "if stage not in STAGES: raise ValueError(stage)" in text(ROOT/"ui/services/pipeline_service.py")
def test_all_stage_routes_are_exposed_by_command_center():
 src=text(ROOT/"command_center/web.py"); assert "/api/datasets/{did}/stage/{name}" in src
 for stage in EXPECTED_STAGES: assert stage in text(ROOT/"command_center/service.py")
def test_stop_route_exists(): assert "/api/datasets/{did}/stop" in text(ROOT/"command_center/web.py")
def test_dataset_routes_cover_list_create_get_ingest():
 src=text(ROOT/"command_center/web.py")
 for route in ["/api/datasets","/api/datasets/{did}","/api/datasets/{did}/ingest"]: assert route in src
def test_group_route_exists(): assert "/api/groups" in text(ROOT/"command_center/web.py")
def test_system_route_exists(): assert "/api/system" in text(ROOT/"command_center/web.py")
def test_credential_routes_cover_list_set_test_delete():
 src=text(ROOT/"command_center/web.py")
 for route in ["/api/credentials","/api/credentials/{name}/test","/api/credentials/{name}"]: assert route in src
def test_credential_presets_are_exactly_the_four_required_slots():
 src=text(ROOT/"ui/screens/credentials.py")
 for name,(provider,env) in EXPECTED_CREDS.items(): assert f'"{name}"' in src and f'"{provider}"' in src and f'"{env}"' in src
def test_backend_is_started_without_browser_by_desktop_launcher():
 src=text(ROOT/"ui/core/application.py"); assert '"--no-browser"' in src and "run_command_center.py" in src
def test_browser_is_not_opened_by_desktop_backend_manager():
 src=text(ROOT/"ui/core/application.py"); assert "--no-browser" in src and "webbrowser" not in src
def test_target_window_geometry_is_1760x990(): assert 'WINDOW_SIZE = "1760x990"' in text(ROOT/"ui/core/config.py")
def test_target_window_has_usable_minimum():
 src=text(ROOT/"ui/core/config.py"); assert "WINDOW_MIN" in src and "1280" in src and "720" in src
def test_visual_theme_is_defined_centrally():
 src=text(ROOT/"ui/core/config.py")
 for name in ["BG","PANEL","PANEL2","LINE","TEXT","MUTED","ACCENT","SUCCESS","ERROR"]: assert re.search(rf"^{name}\s*=",src,re.M)
def test_dataset_selection_navigates_to_pipeline():
 src=text(ROOT/"ui/screens/dataset.py"); assert 'navigation.navigate("Pipeline")' in src and "selected_dataset_id" in src
def test_dataset_creation_is_wired_to_service(): assert "registry.dataset().create" in text(ROOT/"ui/screens/dataset.py")
def test_dataset_ingest_is_wired_to_service(): assert "registry.dataset().ingest" in text(ROOT/"ui/screens/dataset.py")
def test_each_pipeline_stage_has_run_control():
 src=text(ROOT/"ui/screens/pipeline.py"); assert "for i,s in enumerate(STAGES)" in src and "self.run_stage(stage)" in src
def test_pipeline_stop_is_wired(): assert "registry.pipeline().stop(did)" in text(ROOT/"ui/screens/pipeline.py")
def test_credentials_save_is_wired():
 src=text(ROOT/"ui/screens/credentials.py"); assert "registry.credentials().set" in src and "Save / Replace" in src
def test_required_service_modules_exist():
 for service in ["process","system","credential","crawler","dataset","pipeline","training","output","log"]: assert (ROOT/"ui/services"/f"{service}_service.py").exists()
def test_documentation_contains_real_launch_commands():
 readme=text(ROOT/"README.md"); assert "python .\\launch.py" in readme and "run_pipeline.py --doctor" in readme
def test_documentation_mentions_machine_verification_boundary():
 readme=text(ROOT/"README.md"); assert "Windows" in readme and ("1760x990" in readme or "1760×990" in readme)
def test_no_common_secret_literals_are_committed():
 forbidden=["g"+"hp_","github"+"_pat_","AI"+"za"]
 for p in ROOT.rglob("*"):
  if not p.is_file() or ".git" in p.parts or "llama.cpp" in p.parts: continue
  if p.name in {"README.md",".env.example","credentials.example.yaml"} or p.suffix.lower() in {".pyc",".png",".jpg",".jpeg",".gif",".ico",".bin",".pt"}: continue
  data=p.read_text(encoding="utf-8",errors="ignore")
  for token in forbidden: assert token not in data,f"possible secret literal {token} in {p}"
def test_release_docs_exist():
 for name in ["README.md","START_HERE.md","PROJECT_STATE.md","VERIFICATION.md"]: assert (ROOT/name).exists()
def test_machine_verification_suite_is_present():
 assert (ROOT/"tests/model_lab/test_machine_environment.py").exists() and (ROOT/"scripts/run_release_verification.ps1").exists()
def test_traceability_document_exists(): assert (ROOT/"VERIFICATION_CHECKLIST.md").exists()
