This is a prompt.

# If this is the first call this session to this prompt document, start here. Otherwise, move to the next header

Expected call pattern: '.prompts/proceed_with_implementation.md docs/planning/path/to/planningdoc.md'

1. Read the planning doc passed as context. Make note of significant uncertainties. If this is part of a multiphase plan, make sure this is the next phase that should be implemented.
2. Make sure that any decisions requiring developer input have been made.
3. Evaluate the 'freshness' of the plan. Evaluation should include but is not limited to:
    - If the planning doc is part of a multi phase workflow, review the preceding planning doc (potentially in an 'implemented' folder)
    - Review related scripts that will either be modified and any scripts that depend/are dependent on the scripts that will be modified
    - If the implementation relies on existing test functions, review them too
4. Review .prompts/proceed_with_implementation.md
    - if there are discrepencies between the plan and philosphy.md, explain them along with direct quotes from .prompts/philosphy.md
5. If the plan is associated with a master plan, review the master planning document. Note the risk that the master planning document has gone stale. If there are discrepencies, report them to the developer along with direct quotes from this plan and the master plan, and judge which document is more likely to be stale.
6. Provide a 'preflight' report with your findings from 1-5. Recommend whether or not to proceed. Do not proceed with implementation without explicit approval from the developer. The report should start with 1) decisions needing input and all the relevant context to support the decision followed by options and a recommendation and 2) uncertainties requiring clarification posed as a question with all relevant context needed to inform and support the developer's response and 3) other changes your plan on making after the review. The Rest of the report should cover findings from 1-5.

# If this is a subsequent call to this prompt:

Expected call pattern: '.prompts/proceed_with_implementation.md'

1. Summarize all key decisions made in a table for the developer. Recommend whether or not to proceed. Upon approval:
    1. Make sure that all relevant planning documents have been updated to align with the plan.
    2. Proceed with implementation.