// ======================
// DOGNOSIS OUTREACH AUTOMATION - SETUP DOMAIN
// Complete system configuration and initialization
// ======================

const Setup = {
  /**
   * Main setup function - runs complete configuration process
   */
  runInitialSetup: function() {
    console.log("🎯 SETUP: Starting complete system configuration...");
    
    const results = {
      success: true,
      steps: [],
      errors: []
    };
    
    try {
      // Step 1: Validate system prerequisites
      console.log("1️⃣ Validating system prerequisites...");
      const prereqResult = this.validatePrerequisites();
      results.steps.push({ step: "Prerequisites", success: prereqResult.success });
      if (!prereqResult.success) results.errors.push(prereqResult.error);
      
      // Step 2: Configure PhantomBuster
      console.log("2️⃣ Configuring PhantomBuster integration...");
      const pbResult = this.configPhantomBuster();
      results.steps.push({ step: "PhantomBuster", success: pbResult.success });
      if (!pbResult.success) results.errors.push(pbResult.error);
      
      // Step 3: Validate spreadsheet structure
      console.log("3️⃣ Validating spreadsheet structure...");
      const sheetResult = this.validateSpreadsheetStructure();
      results.steps.push({ step: "Spreadsheet", success: sheetResult.success });
      if (!sheetResult.success) results.errors.push(sheetResult.error);
      
      // Step 4: Create tracking columns
      console.log("4️⃣ Creating tracking columns...");
      const columnsResult = this.createTrackingColumns();
      results.steps.push({ step: "Tracking Columns", success: columnsResult.success });
      if (!columnsResult.success) results.errors.push(columnsResult.error);
      
      // Step 5: Validate sequence sheets
      console.log("5️⃣ Validating sequence sheets...");
      const sequenceResult = this.validateSequenceSheets();
      results.steps.push({ step: "Sequence Sheets", success: sequenceResult.success });
      if (!sequenceResult.success) results.errors.push(sequenceResult.error);
      
      // Step 6: Setup automation triggers
      console.log("6️⃣ Setting up automation triggers...");
      const triggersResult = this.setupAutomationTriggers();
      results.steps.push({ step: "Automation Triggers", success: triggersResult.success });
      if (!triggersResult.success) results.errors.push(triggersResult.error);
      
      // Step 7: Final system health check
      console.log("7️⃣ Running system health check...");
      const healthResult = this.runSystemHealthCheck();
      results.steps.push({ step: "Health Check", success: healthResult.success });
      if (!healthResult.success) results.errors.push(healthResult.error);
      
      // Determine overall success
      const failedSteps = results.steps.filter(s => !s.success).length;
      results.success = failedSteps === 0;
      
      if (results.success) {
        console.log("✅ Setup completed successfully! System is ready.");
      } else {
        console.log(`⚠️ Setup completed with ${failedSteps} issues. See error details.`);
        results.errors.forEach(error => console.log(`   ❌ ${error}`));
      }
      
      return results;
      
    } catch (error) {
      console.log(`💥 Critical setup error: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Validate system prerequisites
   */
  validatePrerequisites: function() {
    try {
      const issues = [];
      
      // Check Gmail quota
      try {
        MailApp.getRemainingDailyQuota();
        if (MailApp.getRemainingDailyQuota() < VALIDATION.MIN_GMAIL_QUOTA) {
          issues.push("Gmail quota too low");
        }
      } catch (e) {
        issues.push("Gmail access not available");
      }
      
      // Check Google Sheets access
      try {
        const ss = SpreadsheetApp.getActiveSpreadsheet();
        if (!ss) issues.push("No active spreadsheet found");
      } catch (e) {
        issues.push("Spreadsheet access denied");
      }
      
      // Check Properties Service
      try {
        PropertiesService.getScriptProperties().getProperty("test");
      } catch (e) {
        issues.push("Properties Service access denied");
      }
      
      if (issues.length > 0) {
        return { success: false, error: `Prerequisites failed: ${issues.join(", ")}` };
      }
      
      console.log("   ✅ All prerequisites met");
      return { success: true };
      
    } catch (error) {
      return { success: false, error: `Prerequisites check failed: ${error.toString()}` };
    }
  },
  
  /**
   * Configure PhantomBuster integration
   */
  configPhantomBuster: function() {
    try {
      // Check if already configured and valid
      const existingConfig = Services.getProperty('phantombuster_config');
      if (existingConfig) {
        console.log("   ℹ️ PhantomBuster config exists, validating...");
        const validation = this.validatePhantomBusterConfig();
        if (validation.success) {
          console.log("   ✅ PhantomBuster configuration is valid");
          return validation;
        } else {
          console.log("   ⚠️ Existing config is incomplete, attempting to fix...");
          // Continue with auto-detection to fix incomplete config
        }
      }
      
      // Try to auto-detect individual properties and combine them
      console.log("   🔍 Checking for existing PhantomBuster properties...");
      const autoConfig = this.autoDetectPhantomBusterProperties();
      if (autoConfig.success) {
        console.log("   ✅ Auto-detected and combined existing PhantomBuster properties");
        return this.validatePhantomBusterConfig();
      }
      
      // If auto-detection failed, try manual combination of common property names
      console.log("   🔍 Auto-detection failed, trying manual combination...");
      const manualConfig = this.combineKnownPropertyNames();
      if (manualConfig.success) {
        console.log("   ✅ Manually combined existing PhantomBuster properties");
        return this.validatePhantomBusterConfig();
      }
      
      // If all detection methods fail, show manual instructions
      console.log("   ⚠️ PhantomBuster properties not found automatically.");
      console.log("   📋 Please ensure your PhantomBuster properties are stored in Script Properties:");
      console.log("      • PB_API_KEY");
      console.log("      • PB_NETWORK_BOOSTER_ID");
      console.log("      • PB_MESSAGE_SENDER_ID");
      console.log("      • LINKEDIN_SESSION_COOKIE");
      console.log("   🔧 Then re-run: runInitialSetup()");
      
      return { success: false, error: "PhantomBuster properties not found", requiresManualSetup: true };
      
    } catch (error) {
      return { success: false, error: `PhantomBuster config failed: ${error.toString()}` };
    }
  },

  /**
   * Debug function to show all properties that might be PhantomBuster related
   */
  debugPhantomBusterProperties: function() {
    try {
      const allProps = PropertiesService.getScriptProperties().getProperties();
      const keys = Object.keys(allProps);
      
      console.log(`🔍 DEBUG: Found ${keys.length} total properties`);
      console.log("📋 All property keys:");
      keys.forEach(key => {
        console.log(`   ${key}`);
      });
      
      // Look for PhantomBuster-related properties
      const phantomKeys = keys.filter(key => 
        key.toLowerCase().includes('phantom') ||
        key.toLowerCase().includes('api') ||
        key.toLowerCase().includes('linkedin') ||
        key.toLowerCase().includes('cookie') ||
        key.toLowerCase().includes('booster') ||
        key.toLowerCase().includes('message') ||
        key.toLowerCase().includes('network') ||
        key.toLowerCase().includes('pb_') ||
        key.toLowerCase().startsWith('pb')
      );
      
      console.log(`\n🎯 PhantomBuster-related properties (${phantomKeys.length}):`);
      phantomKeys.forEach(key => {
        const value = allProps[key];
        const preview = value && value.length > 30 ? value.substring(0, 30) + "..." : value;
        console.log(`   ${key}: ${preview}`);
      });
      
      return { keys: keys, phantomKeys: phantomKeys };
      
    } catch (error) {
      console.log(`❌ Debug error: ${error.toString()}`);
      return { error: error.toString() };
    }
  },

  /**
   * Auto-detect individual PhantomBuster properties and combine them
   */
  autoDetectPhantomBusterProperties: function() {
    try {
      const properties = Services.getProperty('all') || {};
      const allProps = PropertiesService.getScriptProperties().getProperties();
      const keys = Object.keys(allProps);
      
      // Look for PhantomBuster-related properties
      const phantomKeys = keys.filter(key => 
        key.toLowerCase().includes('phantom') ||
        key.toLowerCase().includes('api') ||
        key.toLowerCase().includes('linkedin') ||
        key.toLowerCase().includes('cookie') ||
        key.toLowerCase().includes('booster') ||
        key.toLowerCase().includes('message') ||
        key.toLowerCase().includes('network')
      );
      
      if (phantomKeys.length === 0) {
        return { success: false, message: "No PhantomBuster properties found" };
      }
      
      console.log(`   📋 Found ${phantomKeys.length} potential properties: ${phantomKeys.join(', ')}`);
      
      // Try to identify the specific ones we need
      const config = {};
      let foundCount = 0;
      
      // Look for API key (more flexible patterns)
      const apiKeyProps = phantomKeys.filter(key => 
        (key.toLowerCase().includes('api') && key.toLowerCase().includes('key')) ||
        key.toLowerCase() === 'api_key' ||
        key.toLowerCase() === 'apikey' ||
        key.toLowerCase() === 'pb_api_key' ||
        key.toLowerCase().includes('phantombuster_api') ||
        key.toLowerCase().includes('phantom_api') ||
        key.toLowerCase().startsWith('pb_api')
      );
      if (apiKeyProps.length > 0) {
        config.apiKey = allProps[apiKeyProps[0]];
        console.log(`   ✅ Found API Key: ${apiKeyProps[0]}`);
        foundCount++;
      }
      
      // Look for Network Booster ID (more flexible patterns)
      const networkProps = phantomKeys.filter(key => 
        key.toLowerCase().includes('network') || 
        key.toLowerCase().includes('booster') ||
        key.toLowerCase() === 'network_booster_id' ||
        key.toLowerCase() === 'networkboosterid' ||
        key.toLowerCase().startsWith('pb_network') ||
        key.toLowerCase().startsWith('pb_booster') ||
        key.toLowerCase().includes('phantom_network')
      );
      if (networkProps.length > 0) {
        config.networkBoosterId = allProps[networkProps[0]];
        console.log(`   ✅ Found Network Booster: ${networkProps[0]}`);
        foundCount++;
      }
      
      // Look for Message Sender ID (more flexible patterns)
      const messageProps = phantomKeys.filter(key => 
        (key.toLowerCase().includes('message') && !key.toLowerCase().includes('network')) ||
        key.toLowerCase() === 'message_sender_id' ||
        key.toLowerCase() === 'messagesenderid' ||
        key.toLowerCase().startsWith('pb_message') ||
        key.toLowerCase().startsWith('pb_sender') ||
        key.toLowerCase().includes('phantom_message')
      );
      if (messageProps.length > 0) {
        config.messageSenderId = allProps[messageProps[0]];
        console.log(`   ✅ Found Message Sender: ${messageProps[0]}`);
        foundCount++;
      }
      
      // Look for LinkedIn Cookie (more flexible patterns)
      const cookieProps = phantomKeys.filter(key => 
        key.toLowerCase().includes('cookie') || 
        key.toLowerCase() === 'linkedin_cookie' ||
        key.toLowerCase() === 'linkedincookie' ||
        key.toLowerCase() === 'linkedin_session_cookie' ||
        key.toLowerCase() === 'li_at' ||
        key.toLowerCase() === 'li_at_cookie' ||
        key.toLowerCase().startsWith('pb_cookie') ||
        key.toLowerCase().startsWith('pb_linkedin') ||
        (key.toLowerCase().includes('linkedin') && !key.toLowerCase().includes('message') && !key.toLowerCase().includes('network'))
      );
      if (cookieProps.length > 0) {
        config.linkedinCookie = allProps[cookieProps[0]];
        console.log(`   ✅ Found LinkedIn Cookie: ${cookieProps[0]}`);
        foundCount++;
      }
      
      if (foundCount >= 2) {
        // Save combined config
        Services.setProperty('phantombuster_config', JSON.stringify(config));
        console.log(`   🔧 Combined ${foundCount}/4 properties into phantombuster_config`);
        return { success: true, foundCount: foundCount };
      } else {
        return { success: false, message: `Only found ${foundCount}/4 required properties` };
      }
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },

  /**
   * Try to combine properties using known common naming patterns
   */
  combineKnownPropertyNames: function() {
    try {
      const allProps = PropertiesService.getScriptProperties().getProperties();
      
      // Check for common property name patterns
      const knownPatterns = [
        // Pattern 1: PB_ prefix (user's current naming)
        {
          apiKey: 'PB_API_KEY',
          networkBoosterId: 'PB_NETWORK_BOOSTER_ID', 
          messageSenderId: 'PB_MESSAGE_SENDER_ID',
          linkedinCookie: 'LINKEDIN_SESSION_COOKIE'
        },
        // Pattern 2: All uppercase with underscores
        {
          apiKey: 'API_KEY',
          networkBoosterId: 'NETWORK_BOOSTER_ID',
          messageSenderId: 'MESSAGE_SENDER_ID', 
          linkedinCookie: 'LINKEDIN_COOKIE'
        },
        // Pattern 3: Lowercase with underscores
        {
          apiKey: 'api_key',
          networkBoosterId: 'network_booster_id',
          messageSenderId: 'message_sender_id',
          linkedinCookie: 'linkedin_cookie'
        }
      ];
      
      for (const pattern of knownPatterns) {
        const config = {
          apiKey: allProps[pattern.apiKey] || '',
          networkBoosterId: allProps[pattern.networkBoosterId] || '',
          messageSenderId: allProps[pattern.messageSenderId] || '',
          linkedinCookie: allProps[pattern.linkedinCookie] || ''
        };
        
        // Count how many properties we found with this pattern
        const foundCount = Object.values(config).filter(val => val !== '').length;
        
        if (foundCount >= 3) { // Need at least 3 out of 4 properties
          console.log(`   🔧 Found ${foundCount}/4 properties using pattern:`)
          console.log(`      API Key: ${config.apiKey ? '✅' : '❌'} (${pattern.apiKey})`);
          console.log(`      Network Booster: ${config.networkBoosterId ? '✅' : '❌'} (${pattern.networkBoosterId})`);
          console.log(`      Message Sender: ${config.messageSenderId ? '✅' : '❌'} (${pattern.messageSenderId})`);
          console.log(`      LinkedIn Cookie: ${config.linkedinCookie ? '✅' : '❌'} (${pattern.linkedinCookie})`);
          
          // Save combined config
          Services.setProperty('phantombuster_config', JSON.stringify(config));
          console.log(`   🔧 Combined ${foundCount}/4 properties into phantombuster_config`);
          
          return { success: true, foundCount: foundCount, pattern: pattern };
        }
      }
      
      return { success: false, message: "No matching property patterns found" };
      
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },

  
  /**
   * Validate PhantomBuster configuration
   */
  validatePhantomBusterConfig: function() {
    try {
      const config = Services.getProperty('phantombuster_config');
      if (!config) {
        return { success: false, error: "No PhantomBuster configuration found" };
      }
      
      const parsedConfig = JSON.parse(config);
      const required = ['apiKey', 'networkBoosterId', 'messageSenderId'];
      
      for (const field of required) {
        if (!parsedConfig[field]) {
          return { success: false, error: `Missing PhantomBuster ${field}` };
        }
      }
      
      console.log("   ✅ PhantomBuster configuration valid");
      return { success: true };
      
    } catch (error) {
      return { success: false, error: `PhantomBuster validation failed: ${error.toString()}` };
    }
  },
  
  /**
   * Validate spreadsheet structure
   */
  validateSpreadsheetStructure: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      
      if (!contactSheet) {
        return { success: false, error: "ContactList sheet not found" };
      }
      
      const headers = contactSheet.getRange(1, 1, 1, contactSheet.getLastColumn()).getValues()[0];
      const missingColumns = [];
      
      for (const requiredCol of VALIDATION.REQUIRED_COLUMNS) {
        if (!headers.includes(requiredCol)) {
          missingColumns.push(requiredCol);
        }
      }
      
      if (missingColumns.length > 0) {
        return { success: false, error: `Missing columns: ${missingColumns.join(", ")}` };
      }
      
      console.log("   ✅ Spreadsheet structure valid");
      return { success: true };
      
    } catch (error) {
      return { success: false, error: `Spreadsheet validation failed: ${error.toString()}` };
    }
  },
  
  /**
   * Create tracking columns for all sequences
   */
  createTrackingColumns: function() {
    try {
      // Get all sequence sheets
      const sequenceSheets = Services.getAllSequenceSheets();
      let columnsCreated = 0;
      
      for (const sheetName of sequenceSheets) {
        const trackingColumns = Services.getSequenceTrackingColumns(sheetName);
        const result = Services.createMissingTrackingColumns(trackingColumns);
        if (result.success) {
          columnsCreated += result.columnsCreated || 0;
        }
      }
      
      console.log(`   ✅ Created ${columnsCreated} tracking columns`);
      return { success: true, columnsCreated };
      
    } catch (error) {
      return { success: false, error: `Tracking columns creation failed: ${error.toString()}` };
    }
  },
  
  /**
   * Validate all sequence sheets
   */
  validateSequenceSheets: function() {
    try {
      const sequenceSheets = Services.getAllSequenceSheets();
      const issues = [];
      
      for (const sheetName of sequenceSheets) {
        const validation = Services.validateSequenceSheet(sheetName);
        if (!validation.valid) {
          issues.push(`${sheetName}: ${validation.issues.join(", ")}`);
        }
      }
      
      if (issues.length > 0) {
        return { success: false, error: `Sequence issues: ${issues.join("; ")}` };
      }
      
      console.log(`   ✅ All ${sequenceSheets.length} sequence sheets valid`);
      return { success: true, sequenceCount: sequenceSheets.length };
      
    } catch (error) {
      return { success: false, error: `Sequence validation failed: ${error.toString()}` };
    }
  },
  
  /**
   * Setup automation triggers
   */
  setupAutomationTriggers: function() {
    try {
      // Delete existing triggers first
      const existingTriggers = ScriptApp.getProjectTriggers();
      for (const trigger of existingTriggers) {
        ScriptApp.deleteTrigger(trigger);
      }
      
      // Create daily automation trigger
      ScriptApp.newTrigger('Orchestrator.runDailyAutomation')
        .timeBased()
        .everyHours(24)
        .create();
      
      console.log("   ✅ Automation triggers configured");
      return { success: true };
      
    } catch (error) {
      return { success: false, error: `Triggers setup failed: ${error.toString()}` };
    }
  },
  
  /**
   * Run comprehensive system health check
   */
  runSystemHealthCheck: function() {
    try {
      const healthChecks = [];
      
      // Check Gmail
      const gmailQuota = MailApp.getRemainingDailyQuota();
      healthChecks.push({
        component: "Gmail",
        healthy: gmailQuota > VALIDATION.MIN_GMAIL_QUOTA,
        details: `${gmailQuota} emails remaining today`
      });
      
      // Check PhantomBuster
      const pbConfig = Services.getProperty('phantombuster_config');
      healthChecks.push({
        component: "PhantomBuster",
        healthy: !!pbConfig,
        details: pbConfig ? "Configured" : "Not configured"
      });
      
      // Check Spreadsheet
      try {
        const ss = SpreadsheetApp.getActiveSpreadsheet();
        const contactSheet = ss.getSheetByName("ContactList");
        const contactCount = contactSheet.getLastRow() - 1;
        
        healthChecks.push({
          component: "Spreadsheet", 
          healthy: contactCount > 0,
          details: `${contactCount} contacts found`
        });
      } catch (e) {
        healthChecks.push({
          component: "Spreadsheet",
          healthy: false,
          details: "Access error"
        });
      }
      
      const unhealthyComponents = healthChecks.filter(c => !c.healthy);
      
      if (unhealthyComponents.length > 0) {
        const issues = unhealthyComponents.map(c => `${c.component}: ${c.details}`).join(", ");
        return { success: false, error: `Health check failed: ${issues}` };
      }
      
      console.log("   ✅ All system components healthy");
      return { success: true, healthChecks };
      
    } catch (error) {
      return { success: false, error: `Health check failed: ${error.toString()}` };
    }
  }
};

// Top-level functions for Apps Script dropdown visibility
function runInitialSetup() {
  return Setup.runInitialSetup();
}

function debugPhantomBusterProperties() {
  return Setup.debugPhantomBusterProperties();
}

function testPhantomBusterConnection() {
  try {
    const config = Services.getProperty('phantombuster_config');
    if (!config) {
      console.log("❌ No PhantomBuster config found");
      return { success: false, error: "No config found" };
    }
    
    const parsedConfig = JSON.parse(config);
    console.log("🔧 Testing PhantomBuster API connection...");
    console.log(`   API Key: ${parsedConfig.apiKey ? '***' + parsedConfig.apiKey.slice(-4) : 'Missing'}`);
    
    // Test the actual agent endpoints we use
    const agentId = parsedConfig.networkBoosterId || parsedConfig.messageSenderId;
    if (!agentId) {
      console.log("   ❌ No agent IDs found in configuration");
      return { success: false, message: "Missing agent IDs" };
    }
    
    console.log(`   Testing with agent: ${agentId}`);
    
    // Test the actual endpoints we use for agent operations
    const endpoints = [
      `https://api.phantombuster.com/api/v1/agent/${agentId}`,  // Get agent info (v1)
      `https://api.phantombuster.com/api/v1/agent/${agentId}/launch`,  // Launch endpoint (POST)
      `https://api.phantombuster.com/api/v2/agents/${agentId}`,  // Try v2 as backup
      `https://phantombuster.com/api/v1/agent/${agentId}`
    ];
    
    let response = null;
    let workingEndpoint = null;
    
    for (const endpoint of endpoints) {
      try {
        console.log(`   🔍 Trying: ${endpoint}`);
        
        // Try different authentication methods for this endpoint
        const authHeaders = [
          { 'X-Phantombuster-Key': parsedConfig.apiKey },
          { 'Authorization': `Bearer ${parsedConfig.apiKey}` },
          { 'X-Phantombuster-Key': parsedConfig.apiKey, 'Content-Type': 'application/json' }
        ];
        
        let bestResponse = null;
        for (const headers of authHeaders) {
          try {
            // Skip /launch endpoints in test (they require POST with payload)
            if (endpoint.includes('/launch')) {
              console.log(`      ⏩ Skipping launch endpoint test (requires POST)`);
              continue;
            }
            
            response = UrlFetchApp.fetch(endpoint, {
              method: 'GET',
              headers: { ...headers, 'Accept': 'application/json' },
              muteHttpExceptions: true
            });
            
            const contentType = response.getHeaders()['Content-Type'] || '';
            if (response.getResponseCode() === 200 && contentType.includes('application/json')) {
              console.log(`   ✅ Success with auth: ${Object.keys(headers)[0]}`);
              workingEndpoint = endpoint;
              break;
            }
            
            // Save the best response (200 status even if HTML)
            if (response.getResponseCode() === 200) {
              bestResponse = response;
            }
            
          } catch (e) {
            console.log(`   Auth method failed: ${e.toString().substring(0, 100)}`);
          }
        }
        
        // Use best response if no JSON response found
        if (!workingEndpoint && bestResponse) {
          response = bestResponse;
        }
        
        if (response.getResponseCode() === 200) {
          workingEndpoint = endpoint;
          console.log(`   ✅ Found working endpoint: ${endpoint}`);
          break;
        } else {
          console.log(`   ❌ ${endpoint}: ${response.getResponseCode()}`);
        }
      } catch (e) {
        console.log(`   ❌ ${endpoint}: ${e.toString()}`);
      }
    }
    
    if (workingEndpoint && response.getResponseCode() === 200) {
      const contentText = response.getContentText();
      const contentType = response.getHeaders()['Content-Type'] || '';
      
      console.log(`   📋 Response Content-Type: ${contentType}`);
      console.log(`   📋 Response preview: ${contentText.substring(0, 200)}...`);
      
      if (contentType.includes('application/json')) {
        try {
          const data = JSON.parse(contentText);
          console.log(`   ✅ API Connection successful with ${workingEndpoint}`);
          console.log(`   📊 Found ${data.length || 0} agents`);
          return { success: true, agents: data.length || 0, endpoint: workingEndpoint };
        } catch (e) {
          console.log(`   ❌ JSON parse error: ${e.toString()}`);
          return { success: false, error: "Invalid JSON response", details: contentText.substring(0, 500) };
        }
      } else {
        console.log(`   ⚠️ Endpoint returns HTML, likely authentication issue`);
        return { success: false, error: "HTML response (authentication failed)", details: contentText.substring(0, 500) };
      }
    } else {
      console.log(`   ❌ All API endpoints failed`);
      if (response) {
        console.log(`   Last response: ${response.getResponseCode()}`);
        console.log(`   Error preview: ${response.getContentText().substring(0, 200)}`);
      }
      return { success: false, error: "All endpoints failed", details: response ? response.getContentText().substring(0, 200) : "No response" };
    }
    
  } catch (error) {
    console.log(`❌ Connection test failed: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

function combineExistingPhantomBusterProperties() {
  try {
    const allProps = PropertiesService.getScriptProperties().getProperties();
    
    const config = {
      apiKey: allProps['PB_API_KEY'] || '',
      networkBoosterId: allProps['PB_NETWORK_BOOSTER_ID'] || '',
      messageSenderId: allProps['PB_MESSAGE_SENDER_ID'] || '',
      linkedinCookie: allProps['LINKEDIN_SESSION_COOKIE'] || ''
    };
    
    console.log('🔧 MANUALLY COMBINING PHANTOMBUSTER PROPERTIES:');
    console.log(`   API Key: ${config.apiKey ? 'Found' : 'Missing'}`);
    console.log(`   Network Booster: ${config.networkBoosterId ? 'Found' : 'Missing'}`);
    console.log(`   Message Sender: ${config.messageSenderId ? 'Found' : 'Missing'}`);
    console.log(`   LinkedIn Cookie: ${config.linkedinCookie ? 'Found' : 'Missing'}`);
    
    // Save combined config
    PropertiesService.getScriptProperties().setProperty('phantombuster_config', JSON.stringify(config));
    
    console.log('✅ PhantomBuster configuration manually combined!');
    console.log('🔧 Now run: runInitialSetup() to complete setup');
    
    return { success: true, config: config };
    
  } catch (error) {
    console.log(`❌ Error combining properties: ${error.toString()}`);
    return { success: false, error: error.toString() };
  }
}

// Legacy function support for backwards compatibility during transition
function runInitialConfig() {
  console.log("ℹ️ Legacy function called - redirecting to Setup.runInitialSetup()");
  return Setup.runInitialSetup();
}

// Legacy function for backwards compatibility - now redirects to main setup
function setupPhantomBusterInteractive() {
  console.log("ℹ️ setupPhantomBusterInteractive() is deprecated");
  console.log("🚀 PhantomBuster is now auto-detected during runInitialSetup()");
  console.log("💡 Please run: runInitialSetup() for complete system configuration");
  return { success: false, deprecated: true, message: "Use runInitialSetup() instead" };
}

function setupPhantomBusterConfig() {
  return setupPhantomBusterInteractive();
}