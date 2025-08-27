/*
==============================================
DOGNOSIS OUTREACH AUTOMATION - HOW TO RUN
==============================================

==============================================
ENHANCED LINKEDIN + APOLLO HYBRID PROCESS
==============================================

OVERVIEW: Next-Generation Prospect List Generation
This enhanced 7-step process combines LinkedIn's comprehensive coverage with Apollo's enrichment
capabilities, using AI categorization to ensure consistent quality. Achieves ~95% director+ coverage
while reducing manual effort by 67% compared to traditional methods.

CONTACT LIST GENERATION WORKFLOW:

Step 1: LinkedIn PhantomBuster Pulls (Parallel Execution)
        → Use 18_LinkedInUrlGenerator.js to generate targeted LinkedIn URLs
        → Execute 21 searches (7 companies × 3 categories) via PhantomBuster
        → Quality Controls:
          • Filter for "Current Company" only in PhantomBuster settings
          • Standardize company names (e.g., "GRAIL" = "Grail" = "GRAIL, Inc.")
          • Export with timestamp to track data freshness
        → Output: Raw LinkedIn employee lists with titles + company data

Step 2: Apollo Bulk Capture (Parallel Execution)
        → Run simultaneously with LinkedIn pulls for efficiency
        → Filter Settings:
          • Current employees only (employment end date = blank)
          • All job levels initially (AI will filter later)
          • Standardized company names matching LinkedIn format
        → Use Top 10 broad keywords: director, president, chief, officer, head, etc.
        → Export all available fields: email, phone, LinkedIn URL, last updated
        → Output: Enriched Apollo contact database

Step 3: AI-Powered Categorization & Validation
        → Batch process both datasets together for consistency
        → Dual Classification:
          • Seniority: Director+ level (Yes/No)
          • Function: G&A-Exec, R&D, Commercial, Operations, N/A
        → Quality Controls:
          • Manually verify 5% random sample
          • Create edge case rules for ambiguous titles
          • Track categorization confidence scores
        → Output: Both lists with Category and Seniority columns added

Step 4: Smart Cross-Reference & Gap Analysis
        → Multi-Field Matching Logic:
          • LinkedIn URL exact match
          • (First + Last Name + Company) match
          • (Email domain + fuzzy name match) ≥ 85% similarity
        → Handle Variations:
          • Name nicknames (Bob = Robert, etc.)
          • Company subsidiaries/divisions
          • Title variations (VP = Vice President)
        → Output: Gap analysis report + LinkedIn-only prospect list

Step 5: Targeted Enrichment Pipeline
        → Priority Scoring (enrich in this order):
          1. C-suite executives (highest value)
          2. VP/SVP level (decision makers)
          3. Senior Directors (influencers)
          4. Directors (standard priority)
        → Enrichment Methods:
          • Apollo manual addition (preferred)
          • Alternative data providers for hard-to-find contacts
          • LinkedIn Sales Navigator for additional details
        → Output: Newly enriched contact records

Step 6: Master List Compilation & QC
        → Merge Datasets: Combine Apollo original + newly enriched
        → Final deduplication pass
        → Data Completeness Check:
          • Flag contacts missing critical fields
          • Identify stale data (last updated > 6 months)
        → Ensure all contacts have valid categories
        → Output: Master contact database with full categorization

Step 7: Sequence Assignment & Campaign Readiness
        → Auto-Assignment Rules:
          • G&A-Exec → Executive sequence (shorter, strategic)
          • R&D → Technical sequence (data-driven, peer references)
          • Commercial → Partnership sequence (ROI focused)
        → Ensure all merge fields populated
        → Group by company size, region, or other criteria
        → Output: Campaign-ready contact lists by sequence type

SUCCESS METRICS:
• Coverage: ~1,500 director+ prospects (95% of total population)
• Quality: 95%+ categorization accuracy
• Efficiency: 67% reduction in manual enrichment
• Time Savings: 40+ hours → 12-15 hours total process time

==============================================
SYSTEM OVERVIEW
==============================================

This system automates multi-channel outreach campaigns (email + LinkedIn) using Google Apps Script.
It reads contact data and sequence templates from Google Sheets, personalizes content, sends messages
across multiple channels on scheduled days, tracks replies, and provides performance analytics.

PIPELINE DESCRIPTION:
The Dognosis system operates as a multi-channel outreach automation platform that:
• Reads contact data from optimized Google Sheets structure
• Manages multiple sequence templates (ExecSeq, BDSeq, SalesSeq, etc.)
• Calculates optimal send timing based on campaign start dates and sequence days
• Personalizes content using contact data placeholders ({First Name}, {Company}, etc.)
• Coordinates email delivery through Gmail API with quota management
• Handles LinkedIn connections/messages via PhantomBuster API integration
• Monitors for replies across all channels and updates contact status
• Provides real-time analytics and performance tracking
• Self-heals common issues using intelligent diagnostics

EXECUTION FLOW:
Prospect List Generation → ContactList → Sequence Templates → Content Personalization → Channel Delivery → Reply Tracking → Analytics

==============================================
STEP-BY-STEP EXECUTION GUIDE
==============================================

INITIAL SYSTEM SETUP (Run Once):

Step 1: 01_Setup.js:runInitialSetup()
        → Runs complete system configuration automatically
        → Validates spreadsheet structure and creates missing columns
        → Auto-detects and configures PhantomBuster integration
        → Sets up automation triggers and validates sequences
        → Performs comprehensive system health check

Step 2: 02_Test.js:testSystem() (if needed)
        → Additional system validation after configuration
        → Tests Gmail API connection and quota
        → Validates PhantomBuster API access
        → Verifies all domain objects are loaded

DAILY AUTOMATION PIPELINE (Run Daily):

OPTION A - Complete Automation:
Step 1: 08_Orchestrator.js:runDailyAutomation()
        → Orchestrates the entire daily pipeline automatically
        → Calls all steps below in sequence
        → Handles errors and provides summary report

OPTION B - Manual Step-by-Step:
Step 1: 04_Email.js:checkEmailReplies()
        → Scans Gmail for unread emails from contacts
        → Matches sender emails to ContactList
        → Updates Reply Date, Reply Channel, and Status fields
        → Marks emails as read after processing

Step 2: 05_Campaign.js:runDailyCampaigns()
        → Processes all active campaigns for today
        → Gets contacts ready for outreach
        → Handles email and LinkedIn coordination
        → Groups contacts by sequence day actions

Step 3: 04_Email.js:sendBatchEmails() (called within runDailyCampaigns)
        → Groups email tasks by contact and day
        → Checks Gmail quota before sending
        → Sends personalized emails with reply tracking
        → Updates tracking columns with send timestamps
        → Implements rate limiting and error handling

Step 4: 06_LinkedIn.js:batchLinkedInConnections() (called within runDailyCampaigns)
        → Processes LinkedIn connection requests
        → Uses PhantomBuster Network Booster agent
        → Sends personalized connection messages
        → Tracks connection success rates

Step 5: 06_LinkedIn.js:batchLinkedInMessages() (called within runDailyCampaigns)
        → Sends direct messages to existing connections
        → Uses PhantomBuster Message Sender agent
        → Personalizes message content per contact
        → Updates message tracking columns

MONITORING & ANALYTICS (Run As Needed):

Step 1: 07_Monitor.js:showDashboard()
        → Displays comprehensive system performance
        → Shows campaign metrics and health status
        → Provides real-time automation statistics
        → Aggregates performance across all channels

Step 2: 12_Intelligence.js:getPerformanceInsights()
        → Analyzes performance patterns
        → Identifies best-performing sequences
        → Suggests optimization opportunities
        → Predicts campaign outcomes

MAINTENANCE & TROUBLESHOOTING (Run When Issues Occur):

Step 1: 10_AutoFix.js:runAutoFix()
        → Scans for common system issues
        → Repairs data inconsistencies automatically
        → Fixes missing columns or validation rules
        → Resolves API connection problems

Step 2: 11_SmartBatch.js:runSmartBatch()
        → Optimizes batch processing order
        → Balances workload across time periods
        → Prevents quota exhaustion
        → Improves delivery success rates

==============================================
QUICK START COMMANDS
==============================================

FIRST TIME SETUP:
01_Setup.js:runInitialSetup()                 // Complete system setup (auto-detects PhantomBuster)
02_Test.js:testSystem()                       // Validate configuration

DAILY AUTOMATION:
08_Orchestrator.js:runDailyAutomation()       // Complete daily pipeline
  OR run manually:
04_Email.js:checkEmailReplies()               // Process new replies
05_Campaign.js:runDailyCampaigns()            // Send today's messages

MONITORING:
07_Monitor.js:showDashboard()                 // Performance overview
04_Email.js:getEmailStats()                   // Email metrics
07_Monitor.js:getAutomationStats()            // System metrics

TROUBLESHOOTING:
10_AutoFix.js:runAutoFix()                    // Auto-fix issues
02_Test.js:testSystem()                       // System diagnostics

==============================================
COMPLETE PIPELINE EXECUTION
==============================================

To run the full daily automation pipeline:
1. 04_Email.js:checkEmailReplies()
2. 05_Campaign.js:runDailyCampaigns() (handles all outreach automatically)

To execute all at once: 08_Orchestrator.js:runDailyAutomation()

SYSTEM READY! Use 08_Orchestrator.js:runDailyAutomation() to start.
*/