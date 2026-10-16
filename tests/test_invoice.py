from agents.nodes.reporting import determine_recommendation
from agents.nodes.translation import get_litellm_model_config




def test_missing_erp_data_routes_to_manual_review():
    state = {
        "validation_status": "failed",
        "validation_errors": ["Mock ERP record is missing for this invoice."],
        "human_review_required": False,
    }


    rules = {
        "accepted_currencies": ["USD"],
        "validation_policies": {"auto_approve_confidence_threshold": 0.95},
    }


    assert determine_recommendation(state, ["po_number"], rules) == "manual_review"




def test_litellm_model_config_uses_env_defaults():
    config = get_litellm_model_config()


    assert config["model"]
    assert config["temperature"] == 0
