// ======================
// DOGNOSIS OUTREACH AUTOMATION - CONFIGURATION CONSTANTS
// Central location for all configuration values and constants
// ======================

// COLUMN NAMES - Single source of truth for spreadsheet column references
const COLUMN_NAMES = {
  // Contact Information (A-F) - CRM Order
  FIRST_NAME: "First Name",
  LAST_NAME: "Last Name",
  TITLE: "Title", 
  COMPANY: "Company",
  EMAIL: "Email",
  LINKEDIN_URL: "LinkedIn URL",
  
  // Campaign Management (G-K)
  SEQUENCE: "Sequence",
  CAMPAIGN_START_DATE: "Campaign Start Date",
  STATUS: "Status",
  PRIORITY: "Priority",
  SOURCE: "Source",
  
  // Communication Tracking (L-P)
  LAST_CONTACT_DATE: "Last Contact Date",
  REPLY_DATE: "Reply Date",
  REPLY_CHANNEL: "Reply Channel",
  RESPONSE_TYPE: "Response Type",
  NEXT_ACTION: "Next Action",
  
  // Metadata (Q-S)
  CREATED_DATE: "Created Date",
  LAST_MODIFIED: "Last Modified",
  NOTES: "Notes",
  
  // Legacy support
  MESSAGE_SEQUENCE_SHEET: "Sequence",
  PAUSED: "Status",
  REPLIED_TO_EMAIL: "Reply Channel",
  REPLIED_TO_LINKEDIN: "Reply Channel",
  
  // Dynamic Tracking Columns (generated based on sequence)
  EMAIL_SENT_PATTERN: "Day {day} Email Sent",
  LINKEDIN_CONNECT_SENT_PATTERN: "Day {day} LinkedIn Connect Sent", 
  LINKEDIN_MESSAGE_SENT_PATTERN: "Day {day} LinkedIn DM Sent"
};

// SEQUENCE SHEET COLUMN NAMES - Optimized Structure
const SEQUENCE_COLUMNS = {
  DAY: "Day",
  ACTION_TYPE: "Action Type",
  EMAIL_TYPE: "Email Type",
  SUBJECT: "Subject",
  MESSAGE_CONTENT: "Message Content",
  DESCRIPTION: "Description",
  NOTES: "Notes",
  
  // Legacy support
  STEP: "Action Type",
  BODY: "Message Content",
  TALKING_POINT: "Notes"
};

// TIMING CONSTANTS
const TIMING = {
  // Cache durations (milliseconds)
  SEQUENCE_CACHE_DURATION: 300000,  // 5 minutes
  
  // API retry delays (milliseconds)
  API_RETRY_BASE_DELAY: 5000,      // 5 seconds
  API_RETRY_MAX_DELAY: 30000,      // 30 seconds
  API_RETRY_EXPONENTIAL_DELAY: 60000, // 1 minute
  
  // Automation intervals
  FAST_FORWARD_MINUTE_DELAY: 60000, // 1 minute in fast forward mode
  
  // Rate limiting delays
  EMAIL_BATCH_DELAY: 1000,         // 1 second between emails
  LINKEDIN_BATCH_DELAY: 2000,      // 2 seconds between LinkedIn actions
  SHEETS_API_DELAY: 3000           // 3 seconds between sheet operations
};

// CAMPAIGN LIMITS
const CAMPAIGN_LIMITS = {
  DAILY_START_LIMIT: 10,           // Max contacts to start per day
  MAX_CONTACTS_PER_BATCH: 50,      // Max contacts in one batch operation
  MAX_EMAILS_PER_BATCH: 5,         // Max emails to send in one batch
  MAX_LINKEDIN_CONNECTS_PER_DAY: 20, // LinkedIn connection limit
  MAX_LINKEDIN_MESSAGES_PER_DAY: 50, // LinkedIn message limit
  MAX_SEQUENCE_LENGTH_DAYS: 60,    // Maximum sequence length
  MAX_BATCH_SIZE: 50               // Maximum batch size for operations
};

// PHANTOMBUSTER CONFIGURATION
const PHANTOMBUSTER = {
  API_URL: "https://phantombuster.com/api/v2",
  API_BASE_URL: "https://api.phantombuster.com/api/v1",
  MAX_RETRIES: 3,
  DEFAULT_TIMEOUT: 120000,         // 2 minutes
  PROFILES_PER_LAUNCH: 50,         // Max profiles per PhantomBuster launch
  
  // Agent configuration
  NETWORK_BOOSTER_CONFIG: {
    numberOfProfilesToConnect: 20,
    disableScraping: false
  },
  
  MESSAGE_SENDER_CONFIG: {
    numberOfProfiles: 50
  }
};

// SEQUENCE ACTION TYPES
const ACTION_TYPES = {
  EMAIL: "email",
  LINKEDIN_CONNECT: "linkedin_connect", 
  LINKEDIN_MESSAGE: "linkedin_message"
};

// LINKEDIN DEFAULTS
const LINKEDIN_DEFAULTS = {
  CONNECTION_MESSAGE: "Hi {First Name}, I'd love to connect with you!"
};

// SEQUENCE STEP PATTERNS (for parsing Step column)
const SEQUENCE_STEP_PATTERNS = {
  EMAIL: ["email"],
  LINKEDIN_CONNECT: ["li connect", "linkedin connect", "connect", "connection"],
  LINKEDIN_MESSAGE: ["li message", "linkedin message", "li dm", "linkedin dm", "message", "dm"]
};

// EMAIL REPLY PATTERNS
const EMAIL_REPLY = {
  REPLY_INDICATORS: ["reply", "follow up", "follow-up"],
  NEW_EMAIL_INDICATORS: ["new"],
  THREAD_SEARCH_PATTERNS: [
    "to:{email} from:me subject:\"{subject}\"",
    "to:{email} from:me \"{subject}\"",
    "to:{email} from:me"
  ]
};

// PERSONALIZATION PATTERNS
const PERSONALIZATION = {
  PLACEHOLDERS: {
    FIRST_NAME: ["{{FirstName}}", "{{First Name}}", "{{Name}}", "{{contact.first_name}}"],
    LAST_NAME: ["{{LastName}}", "{{Last Name}}"],
    COMPANY: ["{{Company}}"],
    FULL_NAME: ["{{FullName}}", "{{Full Name}}"]
  }
};

// ERROR HANDLING
const ERROR_HANDLING = {
  MAX_LOG_LENGTH: 1000,           // Max characters in error logs
  CRITICAL_ERROR_EMAIL_SUBJECT: "🚨 Dognosis Automation Critical Error",
  ERROR_LOG_RETENTION_DAYS: 30
};

// SYSTEM VALIDATION
const VALIDATION = {
  REQUIRED_COLUMNS: [
    COLUMN_NAMES.FIRST_NAME,
    COLUMN_NAMES.LAST_NAME,
    COLUMN_NAMES.TITLE,
    COLUMN_NAMES.COMPANY,
    COLUMN_NAMES.EMAIL,
    COLUMN_NAMES.LINKEDIN_URL,
    COLUMN_NAMES.SEQUENCE,
    COLUMN_NAMES.CAMPAIGN_START_DATE,
    COLUMN_NAMES.STATUS
  ],
  
  REQUIRED_SEQUENCE_COLUMNS: [
    SEQUENCE_COLUMNS.DAY,
    SEQUENCE_COLUMNS.ACTION_TYPE
  ],
  
  MIN_GMAIL_QUOTA: 100,           // Minimum daily Gmail sending quota
  MIN_CONTACTS_FOR_BATCH: 1,      // Minimum contacts needed for batch operations
  MAX_CONTACT_BATCH_SIZE: 1000    // Maximum contacts to process at once
};

// UTILITY FUNCTIONS FOR CONSTANTS
const CONSTANTS_UTILS = {
  // Get dynamic column name for tracking
  getTrackingColumnName: function(pattern, day) {
    return pattern.replace("{day}", day);
  },
  
  // Get email tracking column name
  getEmailSentColumn: function(day) {
    return this.getTrackingColumnName(COLUMN_NAMES.EMAIL_SENT_PATTERN, day);
  },
  
  // Get LinkedIn connect tracking column name
  getLinkedInConnectColumn: function(day) {
    return this.getTrackingColumnName(COLUMN_NAMES.LINKEDIN_CONNECT_SENT_PATTERN, day);
  },
  
  // Get LinkedIn message tracking column name  
  getLinkedInMessageColumn: function(day) {
    return this.getTrackingColumnName(COLUMN_NAMES.LINKEDIN_MESSAGE_SENT_PATTERN, day);
  },
  
  // Check if step matches action type
  stepMatchesActionType: function(stepText, actionType) {
    if (!stepText || !actionType) return false;
    
    const patterns = SEQUENCE_STEP_PATTERNS[actionType.toUpperCase()];
    if (!patterns) return false;
    
    const lowerStep = stepText.toLowerCase();
    return patterns.some(pattern => lowerStep.includes(pattern));
  },
  
  // Get all placeholder variations for a field
  getPlaceholderVariations: function(fieldType) {
    return PERSONALIZATION.PLACEHOLDERS[fieldType.toUpperCase()] || [];
  }
};

// Export all constants (for environments that support modules)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    COLUMN_NAMES,
    SEQUENCE_COLUMNS,
    TIMING,
    CAMPAIGN_LIMITS,
    PHANTOMBUSTER,
    ACTION_TYPES,
    LINKEDIN_DEFAULTS,
    SEQUENCE_STEP_PATTERNS,
    EMAIL_REPLY,
    PERSONALIZATION,
    ERROR_HANDLING,
    VALIDATION,
    CONSTANTS_UTILS
  };
}

// For Google Apps Script environment, constants are available globally
console.log("✅ Constants.js loaded - Configuration constants available globally");