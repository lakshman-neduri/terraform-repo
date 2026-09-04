import argparse
import json

from google import genai


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--plan",
        required=True,
        help="Path to Terraform plan JSON"
    )

    parser.add_argument(
        "--workspace",
        required=True,
        help="Terraform workspace"
    )

    args = parser.parse_args()

    # Read Terraform plan JSON
    with open(args.plan, "r") as file:
        plan = json.load(file)

    # Extract resource changes
    changes = []

    for resource in plan.get("resource_changes", []):
        change = resource.get("change", {})
        actions = change.get("actions", [])

        # Ignore resources with no changes
        if actions == ["no-op"]:
            continue

        changes.append({
            "address": resource.get("address"),
            "type": resource.get("type"),
            "actions": actions,
            "before": change.get("before"),
            "after": change.get("after")
        })

    if not changes:
        print("# Terraform AI Review\n")
        print("No infrastructure changes detected.")
        return

    prompt = f"""
You are an expert DevOps engineer reviewing a Terraform plan.

Terraform workspace:
{args.workspace}

Terraform resource changes:

{json.dumps(changes, indent=2)}

Review these changes and provide a concise Markdown report.

## Summary

Explain what infrastructure is changing.

## Risk

Classify the overall risk as one of:

- LOW
- MEDIUM
- HIGH
- CRITICAL

Explain why you selected that risk.

## Important Changes

List the important resource changes.

## Potential Issues

Look for:

- destructive changes
- resource replacements
- security risks
- availability risks
- unexpected configuration changes
- possible cost implications

## Recommendation

Choose one:

- SAFE TO PROCEED
- REVIEW REQUIRED
- HIGH RISK

Only use information present in the Terraform plan.
Do not invent information.
"""

    # Create Gemini client.
    # GEMINI_API_KEY is read automatically from the environment.
    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=prompt
    )

    print(response.text)


if __name__ == "__main__":
    main()