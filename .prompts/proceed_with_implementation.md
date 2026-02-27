This is a prompt.

# If this is the first call this session to this prompt document, start here. Otherwise, move to the next header

Expected call pattern: '.prompts/proceed_with_implementation.md docs/planning/path/to/planningdoc.md'

Delegate the following work to an Opus subagent via the Task tool with `subagent_type: "general-purpose"` and `model: "opus"`. Do not perform this work yourself. Pass the planning doc path and all relevant context in the subagent prompt.

The Opus subagent should:

1. Read the planning doc passed as context. Make note of significant uncertainties. If this is part of a multiphase plan, make sure this is the next phase that should be implemented.
2. Make sure that any decisions requiring developer input have been made.
3. Evaluate the 'freshness' of the plan. Evaluation should include but is not limited to:
    - If the planning doc is part of a multi phase workflow, review the preceding planning doc (potentially in an 'implemented' folder)
    - Review related scripts that will either be modified and any scripts that depend/are dependent on the scripts that will be modified
    - If the implementation relies on existing test functions, review them too
4. Review .prompts/philosphy.md
    - if there are discrepencies between the plan and philosphy.md, explain them along with direct quotes from .prompts/philosphy.md, and provide recommendations on how to handle each discrepency
5. If the plan is associated with a master plan, review the master planning document. Note the risk that the master planning document has gone stale. If there are discrepencies, report them to the developer along with direct quotes from this plan and the master plan, and judge which document is more likely to be stale.
6. Return a 'preflight' report with findings from 1-5. The report should include: 0) Model and/or subagents used; 1) decisions needing input with all relevant context, options, and a recommendation; 2) uncertainties requiring clarification posed as questions with all relevant context; 3) other changes planned after the review that are not already reflected in the planning document. The rest of the report covers findings from 1-5.

Once the Opus subagent returns its report, present it to the developer verbatim and coordinate until given the go-ahead to proceed with implementation. Do not proceed without explicit approval.

# If this is a subsequent call to this prompt:

Expected call pattern: '.prompts/proceed_with_implementation.md'

Handle this phase yourself (Sonnet is appropriate here).

This document does not represent permission to succeed. It is a final check. Do not proceed until you have have gone through all of the steps below.

1. If you are unclear about a decision or uncertainty clarfiication, raise questions now. Otherwise proceed to the next step.
2. If decisions and clarifications have made planning documents stale, update them. 
3. Report to the developer:
    - Summarize updates to planning documents. List and explain each change with relevant snippets from the revised docs.
    - Consider whether the edits uncovered additional decisions or uncertinaites. If so, present them
    - Make a recommendation whether or not to proceed with implementation.
4. Upon explicit approval from the developer, proceed with implementation.