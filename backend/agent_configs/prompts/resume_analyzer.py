"""Prompt template for resume analyzer agent."""

RESUME_ANALYSIS_PROMPT = """
Analyze the following resume and extract structured information:

RESUME CONTENT:
---
{resume_content}
---

TASK:
Extract all relevant information following these guidelines:

1. Basic Information:
   - Candidate name (full name as appears in resume)
   - Current or most recent job title
   - Calculate total years of professional experience

2. Skills Analysis (CRITICAL - Follow proficiency rules):
   Technical Skills:
   - Scan ALL sections: work experience, projects, skills section
   - For EACH skill, determine proficiency level:
     * EXPERT: Used as primary technology across multiple production projects, 3+ years, or clear leadership
     * ADVANCED: Used in production with impact; complex features independently; repeated mentions
     * INTERMEDIATE: Listed or used but not core technology; moderate familiarity
     * BEGINNER: Demos/learning/unclear
   Soft Skills:
   - Extract from descriptions: leadership, communication, teamwork, etc.

3. Work Experience:
   - For each role: company, title, dates [start, end], achievements, technologies (standardized names)
   - Parse dates as strings (e.g., "2020-01")

4. Achievements:
   - Extract QUANTIFIED results: numbers, percentages, time/cost savings
   - Examples: "40% latency reduction", "Managed team of 8", "$2M revenue increase"

5. Education & Certifications:
   - Education as list of strings: "{Degree}, {Institution}, {Year}" (if available)
   - Sort by most recent first, then highest degree first
   - List all professional certifications

6. Location & Work Authorization:
   - Extract location (city/state/country)
   - Determine work authorization/visa status if mentioned
   - Relocate willingness: true/false if stated, otherwise null

OUTPUT FORMAT:
Return ONLY a valid JSON object matching the AnalyzedResume schema.
"""
