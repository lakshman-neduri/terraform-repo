import argparse
import json
import os

from openai import OpenAI


def load_plan(path):
    with open(path, "r") as file:
        return json.load(file)


def extract_changes(plan):
    changes = []

    for resource in plan.get("resource_changes", []):
        change = resource.get("change", {})
        actions = change.get("actions", [])

        if actions == ["no-op"]:
            continue

        changes.append({
            "address": resource.get("address"),
            "type": resource.get("type"),
            "actions": actions,
            "before": change.get("before"),
            "after": change.get("after"),
        })

    return changes


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--plan", required=True)
    parser.add_argument("--workspace", required=True)

    args = parser.parse_args()

    plan = load_plan(args.plan)
    changes = extract_changes(plan)

    if not changes:
        print("# Terraform AI Review\n\nNo infrastructure changes detected.")
        return

    client = OpenAI()

    prompt = f"""
You are a Terraform infrastructure reviewer.

Terraform workspace: {args.workspace}

Review the following Terraform plan changes:

{json.dumps(changes, indent=2)}

Provide a concise Markdown review.

Include:

## Summary
Explain what is changing.

## Risk
Classify the overall risk as LOW, MEDIUM, HIGH, or CRITICAL.
Explain the reason.

## Important Changes
List the significant resource changes.

## Potential Issues
Look specifically for:
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
Do not invent infrastructure details.
"""

    response = client.responses.create(
        model="gpt-5",
        input=prompt,
    )

    print(response.output_text)


if __name__ == "__main__":
    main()