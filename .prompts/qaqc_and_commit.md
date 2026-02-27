This is a prompt to:
1. Review any related planning documents and ensure success criteria were met and that the planning documents reflect the changes made, particularly if deviations from the plan were required for implementation.
    - note discrepencies, and include exact quotes and/or code chunks along with rationale for the differences
    - if a master plan document is associated with this implementation, ensure its freshness as it relates to changes made here
    - Summarize issues in a table
2. Read .prompts/philosphy.md and consider whether the changes align with the project philosphy
    - consider impliciations for the entirety of each script you touched. Philosphy.md is a living document, and this is an opportunity to make sure the entire script, not just the recently implemented work, abides by the project philosphy
    - if there are discrepencies, explain them along with direct quotes from .prompts/philosphy.md
    - Include a numerically indexed table for each item in the section 'Development Philosophy' with one column for whether it was honored, exceptions, issues, and recommendations.
3. Report back with your findings organized into four sections, 'implementation summary','implementation vs plan', 'implementation vs philosphy', 'input needed'. The 'input needed' section should be a bulleted list of all decisions or questions needing input. Provide options and make recommendations for decision.
    - Scope creep may occur as tangential issues are discovered in plan implementation. Consider whether multiple commits are recommended. If so, report under 'Proposed commits' with subheaders that would become the top commit message followed by a table of the files included in the commit along with a summary of the changes in each file.
4. If there are no discrepencies, decisions, uncertainties, or AI decisions made that should be reviewed, request to commit changes. Upon explicit approval, proceed with the commit. Otherwise, coordinate with the developer to reach a resolution. Once a resolution has been reached, propose to commit changes and do so once explicit approval has been granted. 
    - If there are changes that the developer made unrelated to your changes, offer to commit them too. Recommend whether to commit them with the main work or as a separate commit and explain your reasoning. Aproval or disapproval is required before proceeding.