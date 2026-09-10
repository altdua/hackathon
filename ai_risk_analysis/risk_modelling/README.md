# Risk Modelling

Reserved for the future risk modelling implementation. The dashboard displays
this stage as pending until you create `agent.py` here.

Implement `run(input_path, output_dir, config, log)` and return
`{"primary_artifact": "risk_scores.json"}`. The input is the selected previous
stage's primary JSON artifact. Write all outputs inside output_dir. Call
log("message") for progress. See the project README for the full contract.

No risk model or placeholder scores are implemented.
