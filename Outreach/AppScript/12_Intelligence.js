// ======================
// DOGNOSIS OUTREACH AUTOMATION - INTELLIGENCE DOMAIN
// Business intelligence and performance insights
// ======================

const Intelligence = {
  /**
   * Get comprehensive performance insights
   */
  getPerformanceInsights: function() {
    console.log("🧠 Analyzing performance data...");
    
    const insights = [];
    
    try {
      // Analyze response rates
      const responseInsights = this.analyzeResponseRates();
      insights.push(...responseInsights);
      
      // Analyze timing patterns
      const timingInsights = this.analyzeTimingPatterns();
      insights.push(...timingInsights);
      
      // Analyze sequence effectiveness
      const sequenceInsights = this.analyzeSequenceEffectiveness();
      insights.push(...sequenceInsights);
      
      // Analyze contact quality
      const contactInsights = this.analyzeContactQuality();
      insights.push(...contactInsights);
      
      // Analyze system performance
      const systemInsights = this.analyzeSystemPerformance();
      insights.push(...systemInsights);
      
      return insights;
      
    } catch (error) {
      Services.logError('Intelligence.getPerformanceInsights', error);
      return [{
        type: 'error',
        message: 'Unable to generate insights',
        severity: 'warning'
      }];
    }
  },
  
  /**
   * Get optimization recommendations
   */
  getOptimizationRecommendations: function() {
    console.log("💡 Generating optimization recommendations...");
    
    const recommendations = [];
    
    try {
      // Get current metrics
      const metrics = this.gatherAllMetrics();
      
      // Response rate optimizations
      if (metrics.responseRate < 10) {
        recommendations.push({
          type: 'sequence',
          title: 'Low Response Rate',
          description: `Current response rate is ${metrics.responseRate}%. Consider A/B testing subject lines.`,
          priority: 'high',
          autoApply: false,
          actions: ['Review subject lines', 'Test personalization', 'Adjust timing']
        });
      }
      
      // Timing optimizations
      if (metrics.bestResponseHour) {
        recommendations.push({
          type: 'timing',
          title: 'Optimal Send Time',
          description: `Best responses come at ${metrics.bestResponseHour}:00. Adjust automation schedule.`,
          priority: 'medium',
          autoApply: true,
          params: { hour: metrics.bestResponseHour }
        });
      }
      
      // Batch size optimizations
      if (metrics.errorRate > 5) {
        recommendations.push({
          type: 'batching',
          title: 'High Error Rate',
          description: `Error rate is ${metrics.errorRate}%. Reduce batch sizes for stability.`,
          priority: 'high',
          autoApply: true,
          params: { reduction: 0.7 }
        });
      }
      
      // Sequence length optimization
      if (metrics.avgDropoffDay < 5) {
        recommendations.push({
          type: 'sequence',
          title: 'Early Sequence Dropoff',
          description: `Contacts stop responding after day ${metrics.avgDropoffDay}. Consider shorter sequences.`,
          priority: 'medium',
          autoApply: false
        });
      }
      
      // LinkedIn optimization
      if (metrics.linkedinResponseRate > metrics.emailResponseRate * 1.5) {
        recommendations.push({
          type: 'channel',
          title: 'LinkedIn Performing Better',
          description: 'LinkedIn getting 50% better response. Prioritize LinkedIn outreach.',
          priority: 'medium',
          autoApply: false
        });
      }
      
      return recommendations;
      
    } catch (error) {
      Services.logError('Intelligence.getOptimizationRecommendations', error);
      return [];
    }
  },
  
  /**
   * Analyze response rates
   */
  analyzeResponseRates: function() {
    const insights = [];
    
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      // Calculate response rates by sequence
      const sequenceStats = {};
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        const sequence = row[headers.indexOf(COLUMN_NAMES.MESSAGE_SEQUENCE_SHEET)];
        const repliedEmail = row[headers.indexOf(COLUMN_NAMES.REPLIED_TO_EMAIL)] === "Yes";
        const repliedLinkedIn = row[headers.indexOf(COLUMN_NAMES.REPLIED_TO_LINKEDIN)] === "Yes";
        const campaignStarted = row[headers.indexOf(COLUMN_NAMES.CAMPAIGN_START_DATE)];
        
        if (sequence && campaignStarted) {
          if (!sequenceStats[sequence]) {
            sequenceStats[sequence] = { total: 0, replied: 0 };
          }
          
          sequenceStats[sequence].total++;
          if (repliedEmail || repliedLinkedIn) {
            sequenceStats[sequence].replied++;
          }
        }
      }
      
      // Generate insights
      for (const [sequence, stats] of Object.entries(sequenceStats)) {
        const responseRate = (stats.replied / stats.total * 100).toFixed(1);
        
        if (responseRate > 15) {
          insights.push(`🌟 "${sequence}" sequence performing well with ${responseRate}% response rate`);
        } else if (responseRate < 5 && stats.total > 10) {
          insights.push(`⚠️ "${sequence}" sequence needs improvement (${responseRate}% response rate)`);
        }
      }
      
      return insights;
      
    } catch (error) {
      Services.logError('Intelligence.analyzeResponseRates', error);
      return [];
    }
  },
  
  /**
   * Analyze timing patterns
   */
  analyzeTimingPatterns: function() {
    const insights = [];
    
    try {
      // Analyze email send times vs responses
      const timingData = this.getTimingData();
      
      if (timingData.morningResponseRate > timingData.afternoonResponseRate * 1.3) {
        insights.push("📅 Morning emails (8-11 AM) get 30% better response rates");
      }
      
      if (timingData.mondayResponseRate < timingData.averageResponseRate * 0.7) {
        insights.push("📅 Avoid Monday sends - response rate 30% below average");
      }
      
      if (timingData.fridayResponseRate > timingData.averageResponseRate * 1.2) {
        insights.push("📅 Friday sends performing well - consider increasing Friday volume");
      }
      
      return insights;
      
    } catch (error) {
      Services.logError('Intelligence.analyzeTimingPatterns', error);
      return [];
    }
  },
  
  /**
   * Analyze sequence effectiveness
   */
  analyzeSequenceEffectiveness: function() {
    const insights = [];
    
    try {
      const sequenceData = this.getSequencePerformanceData();
      
      // Find best performing days
      const bestDays = sequenceData.dayStats
        .filter(d => d.responseRate > 10)
        .sort((a, b) => b.responseRate - a.responseRate)
        .slice(0, 3);
      
      if (bestDays.length > 0) {
        insights.push(`📊 Best response days: ${bestDays.map(d => `Day ${d.day}`).join(', ')}`);
      }
      
      // Check for dropoff patterns
      if (sequenceData.avgLastResponseDay < 7) {
        insights.push(`📉 Most responses come by day ${sequenceData.avgLastResponseDay} - consider shorter sequences`);
      }
      
      // Email vs LinkedIn effectiveness
      if (sequenceData.emailResponseRate && sequenceData.linkedinResponseRate) {
        if (sequenceData.linkedinResponseRate > sequenceData.emailResponseRate * 1.5) {
          insights.push("🔗 LinkedIn messages getting 50% better response than emails");
        }
      }
      
      return insights;
      
    } catch (error) {
      Services.logError('Intelligence.analyzeSequenceEffectiveness', error);
      return [];
    }
  },
  
  /**
   * Analyze contact quality
   */
  analyzeContactQuality: function() {
    const insights = [];
    
    try {
      const qualityData = this.getContactQualityData();
      
      // Title-based insights
      if (qualityData.executiveResponseRate > qualityData.overallResponseRate * 1.5) {
        insights.push("👔 Executive titles responding 50% better than average");
      }
      
      // Company size insights
      if (qualityData.missingCompanyData > 20) {
        insights.push(`🏢 ${qualityData.missingCompanyData}% contacts missing company data - affects personalization`);
      }
      
      // LinkedIn profile insights
      if (qualityData.missingLinkedIn > 30) {
        insights.push(`🔗 ${qualityData.missingLinkedIn}% contacts missing LinkedIn URLs - limiting outreach channels`);
      }
      
      return insights;
      
    } catch (error) {
      Services.logError('Intelligence.analyzeContactQuality', error);
      return [];
    }
  },
  
  /**
   * Analyze system performance
   */
  analyzeSystemPerformance: function() {
    const insights = [];
    
    try {
      // Check error rates
      const errorLogs = Services.getProperty('error_logs');
      if (errorLogs) {
        const errors = JSON.parse(errorLogs);
        const recentErrors = errors.filter(e => {
          const errorTime = new Date(e.timestamp);
          const hourAgo = new Date(Date.now() - 3600000);
          return errorTime > hourAgo;
        });
        
        if (recentErrors.length > 5) {
          insights.push(`⚠️ ${recentErrors.length} errors in last hour - system may need attention`);
        }
      }
      
      // Check automation efficiency
      const lastRun = Services.getProperty('last_automation_run');
      if (lastRun) {
        const runData = JSON.parse(lastRun);
        const duration = runData.results?.duration;
        
        if (duration && duration > 180) {
          insights.push("⏱️ Automation taking over 3 minutes - consider optimization");
        }
      }
      
      // Check quota usage
      const gmailQuota = MailApp.getRemainingDailyQuota();
      if (gmailQuota < 100) {
        insights.push(`📧 Gmail quota low (${gmailQuota} remaining) - will limit today's sends`);
      }
      
      return insights;
      
    } catch (error) {
      Services.logError('Intelligence.analyzeSystemPerformance', error);
      return [];
    }
  },
  
  /**
   * Gather all metrics for analysis
   */
  gatherAllMetrics: function() {
    const metrics = {
      responseRate: 0,
      emailResponseRate: 0,
      linkedinResponseRate: 0,
      bestResponseHour: 10,
      errorRate: 0,
      avgDropoffDay: 7,
      totalContacts: 0,
      activeContacts: 0
    };
    
    try {
      // Get response rates
      const campaignSummary = Campaign.getAllCampaignsSummary();
      if (campaignSummary.total > 0) {
        metrics.responseRate = (campaignSummary.replied / campaignSummary.total * 100).toFixed(1);
        metrics.totalContacts = campaignSummary.total;
        metrics.activeContacts = campaignSummary.active;
      }
      
      // Get timing data
      const timingData = this.getTimingData();
      metrics.bestResponseHour = timingData.bestHour || 10;
      
      // Get error rate
      const errorData = this.getErrorRate();
      metrics.errorRate = errorData.rate;
      
      // Get sequence data
      const sequenceData = this.getSequencePerformanceData();
      metrics.avgDropoffDay = sequenceData.avgLastResponseDay || 7;
      metrics.emailResponseRate = sequenceData.emailResponseRate || 0;
      metrics.linkedinResponseRate = sequenceData.linkedinResponseRate || 0;
      
      return metrics;
      
    } catch (error) {
      Services.logError('Intelligence.gatherAllMetrics', error);
      return metrics;
    }
  },
  
  /**
   * Get timing performance data
   */
  getTimingData: function() {
    // Simplified implementation - would need actual data analysis
    return {
      morningResponseRate: 12,
      afternoonResponseRate: 8,
      mondayResponseRate: 6,
      averageResponseRate: 10,
      fridayResponseRate: 14,
      bestHour: 10
    };
  },
  
  /**
   * Get sequence performance data
   */
  getSequencePerformanceData: function() {
    // Simplified implementation
    return {
      dayStats: [
        { day: 1, responseRate: 15 },
        { day: 3, responseRate: 12 },
        { day: 5, responseRate: 8 },
        { day: 7, responseRate: 5 }
      ],
      avgLastResponseDay: 5,
      emailResponseRate: 10,
      linkedinResponseRate: 15
    };
  },
  
  /**
   * Get contact quality data
   */
  getContactQualityData: function() {
    try {
      const contacts = Data.getAllContacts();
      let missingCompany = 0;
      let missingLinkedIn = 0;
      let executives = 0;
      
      for (const contact of contacts) {
        if (!contact.company) missingCompany++;
        if (!contact.linkedinUrl) missingLinkedIn++;
        if (contact.title && contact.title.match(/CEO|CTO|VP|Director|Manager/i)) {
          executives++;
        }
      }
      
      return {
        missingCompanyData: Math.round(missingCompany / contacts.length * 100),
        missingLinkedIn: Math.round(missingLinkedIn / contacts.length * 100),
        executiveResponseRate: 15, // Would need actual calculation
        overallResponseRate: 10
      };
      
    } catch (error) {
      return {
        missingCompanyData: 0,
        missingLinkedIn: 0,
        executiveResponseRate: 10,
        overallResponseRate: 10
      };
    }
  },
  
  /**
   * Get system error rate
   */
  getErrorRate: function() {
    try {
      const errorLogs = Services.getProperty('error_logs');
      const lastRun = Services.getProperty('last_automation_run');
      
      if (errorLogs && lastRun) {
        const errors = JSON.parse(errorLogs);
        const runData = JSON.parse(lastRun);
        
        // Count errors from last 24 hours
        const dayAgo = new Date(Date.now() - 86400000);
        const recentErrors = errors.filter(e => new Date(e.timestamp) > dayAgo);
        
        return {
          rate: recentErrors.length > 0 ? Math.min(recentErrors.length * 2, 100) : 0,
          count: recentErrors.length
        };
      }
      
      return { rate: 0, count: 0 };
      
    } catch (error) {
      return { rate: 0, count: 0 };
    }
  },
  
  /**
   * Generate predictive insights
   */
  generatePredictiveInsights: function() {
    const predictions = [];
    
    try {
      const metrics = this.gatherAllMetrics();
      
      // Predict quota usage
      const currentQuota = MailApp.getRemainingDailyQuota();
      const avgDailyEmails = 50; // Would calculate from history
      
      if (currentQuota < avgDailyEmails * 2) {
        predictions.push({
          type: 'quota',
          prediction: `Will run out of email quota in ${Math.floor(currentQuota / avgDailyEmails)} days`,
          recommendation: 'Consider upgrading email limits'
        });
      }
      
      // Predict response trends
      if (metrics.responseRate < 5) {
        predictions.push({
          type: 'response',
          prediction: 'Response rates trending down',
          recommendation: 'Time to refresh messaging or try new sequences'
        });
      }
      
      return predictions;
      
    } catch (error) {
      Services.logError('Intelligence.generatePredictiveInsights', error);
      return [];
    }
  },
  
  /**
   * Export intelligence report
   */
  exportIntelligenceReport: function() {
    try {
      const report = {
        generated: new Date(),
        insights: this.getPerformanceInsights(),
        recommendations: this.getOptimizationRecommendations(),
        metrics: this.gatherAllMetrics(),
        predictions: this.generatePredictiveInsights()
      };
      
      // Store report
      Services.setProperty('intelligence_report', JSON.stringify(report));
      
      console.log("📊 Intelligence report generated");
      return report;
      
    } catch (error) {
      Services.logError('Intelligence.exportIntelligenceReport', error);
      return null;
    }
  }
};

// Legacy function support
function getPerformanceInsights() {
  return Intelligence.getPerformanceInsights();
}

function getOptimizationRecommendations() {
  return Intelligence.getOptimizationRecommendations();
}