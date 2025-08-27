// ======================
// DOGNOSIS OUTREACH AUTOMATION - ORCHESTRATOR DOMAIN
// Main automation coordinator and scheduler
// ======================

const Orchestrator = {
  /**
   * Run daily automation - main entry point for scheduled runs
   */
  runDailyAutomation: function() {
    console.log("🤖 DAILY AUTOMATION STARTING...");
    console.log(`📅 Date: ${new Date().toLocaleString()}`);
    
    const results = {
      success: true,
      startTime: new Date(),
      steps: [],
      errors: []
    };
    
    try {
      // Step 1: System health check
      console.log("1️⃣ Checking system health...");
      const healthCheck = Monitor.getSystemHealth();
      results.steps.push({ step: "Health Check", success: healthCheck.healthy });
      
      if (!healthCheck.healthy) {
        console.log("🔧 System issues detected - attempting auto-fix...");
        AutoFix.selfDiagnoseAndRepair();
      }
      
      // Step 2: Check for replies
      console.log("2️⃣ Checking for replies...");
      const replyCheck = Email.checkForReplies();
      results.steps.push({ 
        step: "Reply Check", 
        success: true,
        details: `${replyCheck.newReplies} new replies found`
      });
      
      // Step 3: Process campaigns
      console.log("3️⃣ Processing campaigns...");
      const campaignResults = Campaign.processDailyCampaigns();
      results.steps.push({
        step: "Campaign Processing",
        success: campaignResults.errors.length === 0,
        details: {
          processed: campaignResults.processed,
          emailsSent: campaignResults.emailsSent,
          linkedinConnects: campaignResults.linkedinConnects,
          linkedinMessages: campaignResults.linkedinMessages
        }
      });
      
      // Step 4: Optimize timing
      console.log("4️⃣ Optimizing campaign timing...");
      const optimization = Campaign.optimizeCampaignTiming();
      results.steps.push({ step: "Optimization", success: true });
      
      // Step 5: Generate report
      console.log("5️⃣ Generating performance report...");
      const report = this.generateDailyReport(results);
      results.steps.push({ step: "Report Generation", success: true });
      
      // Calculate duration
      const endTime = new Date();
      const duration = (endTime - results.startTime) / 1000;
      
      console.log("\n" + "=".repeat(50));
      console.log("✅ DAILY AUTOMATION COMPLETE");
      console.log(`⏱️ Duration: ${Math.round(duration)} seconds`);
      console.log(`📧 Emails sent: ${campaignResults.emailsSent}`);
      console.log(`🤝 LinkedIn connects: ${campaignResults.linkedinConnects}`);
      console.log(`💬 LinkedIn messages: ${campaignResults.linkedinMessages}`);
      console.log("=".repeat(50));
      
      // Store results
      Services.setProperty('last_automation_run', JSON.stringify({
        timestamp: endTime,
        results: results
      }));
      
      return results;
      
    } catch (error) {
      Services.logError('Orchestrator.runDailyAutomation', error);
      results.success = false;
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Run intelligent automation with smart optimization
   */
  runIntelligentAutomation: function() {
    console.log("🧠 INTELLIGENT AUTOMATION STARTING...");
    
    const results = {
      success: true,
      mode: 'intelligent',
      optimizations: [],
      actions: []
    };
    
    try {
      // Get system insights
      const insights = Intelligence.getPerformanceInsights();
      const recommendations = Intelligence.getOptimizationRecommendations();
      
      // Apply smart optimizations
      for (const recommendation of recommendations) {
        if (recommendation.autoApply) {
          const applied = this.applyOptimization(recommendation);
          results.optimizations.push({
            recommendation: recommendation.title,
            applied: applied.success
          });
        }
      }
      
      // Run standard automation with enhancements
      const automationResult = this.runDailyAutomation();
      results.actions = automationResult.steps;
      
      // Smart batch processing
      if (insights.batchingOpportunity) {
        console.log("🚀 Smart batching detected - optimizing...");
        const batchResult = SmartBatch.processOptimalBatches();
        results.actions.push({
          step: "Smart Batching",
          success: batchResult.success,
          details: batchResult.optimizations
        });
      }
      
      results.success = automationResult.success;
      return results;
      
    } catch (error) {
      Services.logError('Orchestrator.runIntelligentAutomation', error);
      results.success = false;
      return results;
    }
  },
  
  /**
   * Emergency stop - pause all automation
   */
  emergencyStop: function() {
    console.log("🛑 EMERGENCY STOP INITIATED");
    
    try {
      // Remove all triggers
      const triggers = ScriptApp.getProjectTriggers();
      for (const trigger of triggers) {
        ScriptApp.deleteTrigger(trigger);
      }
      
      // Pause all active campaigns
      const contacts = Data.getFilteredContacts({ active: true });
      let paused = 0;
      
      for (const contact of contacts) {
        const result = Campaign.pauseCampaign(contact, "Emergency stop");
        if (result.success) paused++;
      }
      
      console.log(`✅ Emergency stop complete:`);
      console.log(`   • ${triggers.length} triggers removed`);
      console.log(`   • ${paused} campaigns paused`);
      
      return { 
        success: true, 
        triggersStopped: triggers.length,
        campaignsPaused: paused
      };
      
    } catch (error) {
      Services.logError('Orchestrator.emergencyStop', error);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Schedule automation runs
   */
  scheduleAutomation: function(options = {}) {
    try {
      const {
        frequency = 'daily',
        hour = 9,
        minute = 0,
        daysOfWeek = [1, 2, 3, 4, 5] // Mon-Fri
      } = options;
      
      // Remove existing automation triggers
      const existingTriggers = ScriptApp.getProjectTriggers();
      for (const trigger of existingTriggers) {
        if (trigger.getHandlerFunction().includes('Automation')) {
          ScriptApp.deleteTrigger(trigger);
        }
      }
      
      // Create new trigger based on frequency
      let newTrigger;
      
      switch (frequency) {
        case 'hourly':
          newTrigger = ScriptApp.newTrigger('Orchestrator.runIntelligentAutomation')
            .timeBased()
            .everyHours(1)
            .create();
          break;
          
        case 'daily':
          newTrigger = ScriptApp.newTrigger('Orchestrator.runIntelligentAutomation')
            .timeBased()
            .atHour(hour)
            .nearMinute(minute)
            .everyDays(1)
            .create();
          break;
          
        case 'weekdays':
          // Create trigger for each weekday
          for (const day of daysOfWeek) {
            ScriptApp.newTrigger('Orchestrator.runIntelligentAutomation')
              .timeBased()
              .onWeekDay(ScriptApp.WeekDay[this.getDayName(day)])
              .atHour(hour)
              .nearMinute(minute)
              .create();
          }
          break;
      }
      
      console.log(`✅ Automation scheduled: ${frequency} at ${hour}:${minute}`);
      return { success: true, frequency, hour, minute };
      
    } catch (error) {
      Services.logError('Orchestrator.scheduleAutomation', error);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Process specific sequence day for all contacts
   */
  processSequenceDay: function(day) {
    console.log(`📅 Processing sequence day ${day}...`);
    
    const results = {
      processed: 0,
      emails: 0,
      linkedinConnects: 0,
      linkedinMessages: 0,
      errors: []
    };
    
    try {
      // Get contacts on this sequence day
      const contacts = this.getContactsOnSequenceDay(day);
      results.processed = contacts.length;
      
      if (contacts.length === 0) {
        console.log(`No contacts ready for day ${day}`);
        return results;
      }
      
      // Group by action type
      const actions = {
        emails: [],
        linkedinConnects: [],
        linkedinMessages: []
      };
      
      for (const contact of contacts) {
        const sequenceConfig = Services.getContactSequenceConfig(contact.sequenceSheet);
        
        if (sequenceConfig.emailDays.includes(day)) {
          actions.emails.push({ contact, day });
        }
        if (sequenceConfig.linkedinConnectDays.includes(day)) {
          actions.linkedinConnects.push({ contact, day });
        }
        if (sequenceConfig.linkedinMessageDays.includes(day)) {
          actions.linkedinMessages.push({ contact, day });
        }
      }
      
      // Process batches
      if (actions.emails.length > 0) {
        const emailResult = Email.batchSendEmails(actions.emails);
        results.emails = emailResult.successCount;
        results.errors.push(...emailResult.errors);
      }
      
      if (actions.linkedinConnects.length > 0) {
        const connectResult = LinkedIn.processConnectionsForToday(actions.linkedinConnects);
        results.linkedinConnects = connectResult.successCount;
        results.errors.push(...connectResult.errors);
      }
      
      if (actions.linkedinMessages.length > 0) {
        const messageResult = LinkedIn.processMessagesForToday(actions.linkedinMessages);
        results.linkedinMessages = messageResult.successCount;
        results.errors.push(...messageResult.errors);
      }
      
      return results;
      
    } catch (error) {
      Services.logError('Orchestrator.processSequenceDay', error, { day });
      results.errors.push(error.toString());
      return results;
    }
  },
  
  /**
   * Get contacts on specific sequence day
   */
  getContactsOnSequenceDay: function(day) {
    const contacts = Data.getFilteredContacts({ 
      active: true, 
      campaignStarted: true 
    });
    
    return contacts.filter(contact => {
      const daysSinceStart = Services.getDaysSinceCampaignStart(contact);
      return daysSinceStart === (day - 1);
    });
  },
  
  /**
   * Apply optimization recommendation
   */
  applyOptimization: function(recommendation) {
    try {
      switch (recommendation.type) {
        case 'timing':
          return this.optimizeTiming(recommendation.params);
          
        case 'batching':
          return this.optimizeBatching(recommendation.params);
          
        case 'sequence':
          return this.optimizeSequence(recommendation.params);
          
        default:
          return { success: false, error: "Unknown optimization type" };
      }
    } catch (error) {
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Optimize timing based on response data
   */
  optimizeTiming: function(params) {
    // Implement timing optimization
    return { success: true };
  },
  
  /**
   * Optimize batching strategy
   */
  optimizeBatching: function(params) {
    // Implement batching optimization
    return { success: true };
  },
  
  /**
   * Optimize sequence flow
   */
  optimizeSequence: function(params) {
    // Implement sequence optimization
    return { success: true };
  },
  
  /**
   * Generate daily performance report
   */
  generateDailyReport: function(automationResults) {
    try {
      const report = {
        date: new Date(),
        summary: Monitor.getComprehensiveStatus(),
        automation: automationResults,
        insights: Intelligence.getPerformanceInsights(),
        recommendations: Intelligence.getOptimizationRecommendations()
      };
      
      // Store report
      Services.setProperty('last_daily_report', JSON.stringify(report));
      
      return report;
      
    } catch (error) {
      Services.logError('Orchestrator.generateDailyReport', error);
      return null;
    }
  },
  
  /**
   * Get day name for trigger creation
   */
  getDayName: function(dayNumber) {
    const days = ['', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];
    return days[dayNumber];
  },
  
  /**
   * Run test automation cycle
   */
  runTestCycle: function() {
    console.log("🧪 Running test automation cycle...");
    
    try {
      // Run with test mode enabled
      Services.setProperty('test_mode', 'true');
      
      const result = this.runDailyAutomation();
      
      // Disable test mode
      Services.setProperty('test_mode', 'false');
      
      return result;
      
    } catch (error) {
      Services.setProperty('test_mode', 'false');
      throw error;
    }
  }
};

// Legacy function mappings
function runDailyAutomation() {
  return Orchestrator.runDailyAutomation();
}

function runCompleteAutomation() {
  return Orchestrator.runIntelligentAutomation();
}

function stopAllAutomation() {
  return Orchestrator.emergencyStop();
}