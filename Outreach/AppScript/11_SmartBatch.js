// ======================
// DOGNOSIS OUTREACH AUTOMATION - SMARTBATCH DOMAIN
// Intelligent batch processing and optimization
// ======================

const SmartBatch = {
  /**
   * Process optimal batches based on system capacity
   */
  processOptimalBatches: function() {
    console.log("🚀 SMART BATCH: Optimizing batch processing...");
    
    const results = {
      success: true,
      batches: [],
      optimizations: [],
      totalProcessed: 0
    };
    
    try {
      // Analyze system capacity
      const capacity = this.analyzeSystemCapacity();
      
      // Get pending work
      const pendingWork = this.getPendingWork();
      
      // Create optimal batches
      const batches = this.createOptimalBatches(pendingWork, capacity);
      
      // Process batches with intelligent timing
      for (const batch of batches) {
        const batchResult = this.processBatch(batch);
        results.batches.push(batchResult);
        results.totalProcessed += batchResult.processed;
        
        // Apply dynamic throttling
        if (batchResult.needsThrottle) {
          console.log("⏸️ Applying smart throttling...");
          Utilities.sleep(this.calculateOptimalDelay(batchResult));
        }
      }
      
      // Generate optimization insights
      results.optimizations = this.generateOptimizationInsights(results.batches);
      
      console.log(`✅ Smart batch complete: ${results.totalProcessed} items processed`);
      return results;
      
    } catch (error) {
      Services.logError('SmartBatch.processOptimalBatches', error);
      results.success = false;
      return results;
    }
  },
  
  /**
   * Analyze current system capacity
   */
  analyzeSystemCapacity: function() {
    const capacity = {
      gmailQuota: MailApp.getRemainingDailyQuota(),
      executionTimeRemaining: this.getExecutionTimeRemaining(),
      memoryUsage: this.estimateMemoryUsage(),
      apiLimits: {
        phantomBuster: this.getPhantomBusterCapacity()
      },
      optimal: true
    };
    
    // Determine optimal batch sizes
    capacity.optimalBatchSizes = {
      email: Math.min(
        Math.floor(capacity.gmailQuota * 0.8), // Use 80% of quota
        CAMPAIGN_LIMITS.MAX_BATCH_SIZE
      ),
      linkedinConnect: Math.min(
        PHANTOMBUSTER.PROFILES_PER_LAUNCH,
        50 // LinkedIn daily limit
      ),
      linkedinMessage: Math.min(
        PHANTOMBUSTER.PROFILES_PER_LAUNCH,
        25 // LinkedIn message limit
      )
    };
    
    // Check if running in optimal conditions
    const currentHour = new Date().getHours();
    capacity.optimal = (
      capacity.gmailQuota > 100 &&
      currentHour >= 8 && currentHour <= 18 // Business hours
    );
    
    return capacity;
  },
  
  /**
   * Get all pending work
   */
  getPendingWork: function() {
    const pending = {
      emails: [],
      linkedinConnects: [],
      linkedinMessages: [],
      total: 0
    };
    
    try {
      // Get email tasks
      const emailContacts = Email.getContactsReadyForEmail();
      pending.emails = emailContacts.map(item => ({
        type: 'email',
        contact: item.contact,
        day: item.day,
        priority: this.calculatePriority(item)
      }));
      
      // Get LinkedIn tasks
      const linkedinTasks = LinkedIn.getContactsReadyForLinkedIn();
      
      pending.linkedinConnects = linkedinTasks.connections.map(item => ({
        type: 'linkedinConnect',
        contact: item.contact,
        day: item.day,
        priority: this.calculatePriority(item)
      }));
      
      pending.linkedinMessages = linkedinTasks.messages.map(item => ({
        type: 'linkedinMessage',
        contact: item.contact,
        day: item.day,
        priority: this.calculatePriority(item)
      }));
      
      pending.total = pending.emails.length + 
                     pending.linkedinConnects.length + 
                     pending.linkedinMessages.length;
      
      console.log(`📋 Found ${pending.total} pending tasks`);
      return pending;
      
    } catch (error) {
      Services.logError('SmartBatch.getPendingWork', error);
      return pending;
    }
  },
  
  /**
   * Create optimal batches based on capacity and priority
   */
  createOptimalBatches: function(pendingWork, capacity) {
    const batches = [];
    
    // Sort by priority (highest first)
    const sortByPriority = (a, b) => b.priority - a.priority;
    
    // Create email batches
    if (pendingWork.emails.length > 0) {
      const emailsSorted = pendingWork.emails.sort(sortByPriority);
      const emailBatches = this.createBatchesOfSize(
        emailsSorted,
        capacity.optimalBatchSizes.email,
        'email'
      );
      batches.push(...emailBatches);
    }
    
    // Create LinkedIn connect batches
    if (pendingWork.linkedinConnects.length > 0) {
      const connectsSorted = pendingWork.linkedinConnects.sort(sortByPriority);
      const connectBatches = this.createBatchesOfSize(
        connectsSorted,
        capacity.optimalBatchSizes.linkedinConnect,
        'linkedinConnect'
      );
      batches.push(...connectBatches);
    }
    
    // Create LinkedIn message batches
    if (pendingWork.linkedinMessages.length > 0) {
      const messagesSorted = pendingWork.linkedinMessages.sort(sortByPriority);
      const messageBatches = this.createBatchesOfSize(
        messagesSorted,
        capacity.optimalBatchSizes.linkedinMessage,
        'linkedinMessage'
      );
      batches.push(...messageBatches);
    }
    
    // Apply intelligent scheduling
    return this.scheduleOptimalBatches(batches, capacity);
  },
  
  /**
   * Create batches of specified size
   */
  createBatchesOfSize: function(items, batchSize, type) {
    const batches = [];
    
    for (let i = 0; i < items.length; i += batchSize) {
      batches.push({
        id: `${type}_batch_${batches.length + 1}`,
        type: type,
        items: items.slice(i, i + batchSize),
        priority: items[i].priority, // Use first item's priority
        estimatedTime: this.estimateProcessingTime(type, Math.min(batchSize, items.length - i))
      });
    }
    
    return batches;
  },
  
  /**
   * Schedule batches for optimal processing
   */
  scheduleOptimalBatches: function(batches, capacity) {
    // If not in optimal time, prioritize critical tasks
    if (!capacity.optimal) {
      return batches
        .filter(batch => batch.priority >= 80) // High priority only
        .slice(0, 3); // Limit batches in non-optimal times
    }
    
    // In optimal conditions, process all batches
    // but order by type for better performance
    const typeOrder = ['email', 'linkedinConnect', 'linkedinMessage'];
    
    return batches.sort((a, b) => {
      // First by type order
      const typeIndexA = typeOrder.indexOf(a.type);
      const typeIndexB = typeOrder.indexOf(b.type);
      if (typeIndexA !== typeIndexB) return typeIndexA - typeIndexB;
      
      // Then by priority
      return b.priority - a.priority;
    });
  },
  
  /**
   * Process a single batch
   */
  processBatch: function(batch) {
    console.log(`📦 Processing ${batch.type} batch: ${batch.items.length} items`);
    
    const result = {
      batchId: batch.id,
      type: batch.type,
      processed: 0,
      errors: [],
      startTime: new Date(),
      needsThrottle: false
    };
    
    try {
      switch (batch.type) {
        case 'email':
          const emailResult = Email.batchSendEmails(
            batch.items.map(item => ({ contact: item.contact, day: item.day }))
          );
          result.processed = emailResult.successCount;
          result.errors = emailResult.errors;
          result.quotaRemaining = emailResult.quota;
          result.needsThrottle = emailResult.quota < 50;
          break;
          
        case 'linkedinConnect':
          const connectResult = LinkedIn.processConnectionsForToday(
            batch.items.map(item => ({ contact: item.contact, day: item.day }))
          );
          result.processed = connectResult.successCount;
          result.errors = connectResult.errors;
          result.phantomBusterId = connectResult.phantomBusterId;
          break;
          
        case 'linkedinMessage':
          const messageResult = LinkedIn.processMessagesForToday(
            batch.items.map(item => ({ contact: item.contact, day: item.day }))
          );
          result.processed = messageResult.successCount;
          result.errors = messageResult.errors;
          result.phantomBusterId = messageResult.phantomBusterId;
          break;
      }
      
      result.endTime = new Date();
      result.duration = (result.endTime - result.startTime) / 1000;
      result.success = result.errors.length === 0;
      
      return result;
      
    } catch (error) {
      Services.logError('SmartBatch.processBatch', error, { batchId: batch.id });
      result.errors.push(error.toString());
      return result;
    }
  },
  
  /**
   * Calculate priority for a task
   */
  calculatePriority: function(task) {
    let priority = 50; // Base priority
    
    // Higher priority for early sequence days
    if (task.day <= 3) priority += 20;
    
    // Higher priority for contacts with high engagement potential
    if (task.contact.title && task.contact.title.toLowerCase().includes('ceo')) {
      priority += 15;
    }
    
    // Higher priority for personalized messages
    if (task.contact.firstName && task.contact.company) {
      priority += 10;
    }
    
    // Lower priority for late in sequence
    if (task.day > 10) priority -= 10;
    
    // Time-based priority (prefer morning sends)
    const currentHour = new Date().getHours();
    if (currentHour >= 8 && currentHour <= 11) {
      priority += 15;
    }
    
    return Math.max(0, Math.min(100, priority));
  },
  
  /**
   * Calculate optimal delay between batches
   */
  calculateOptimalDelay: function(batchResult) {
    let delay = TIMING.BATCH_EMAIL_DELAY;
    
    // Increase delay if quota is low
    if (batchResult.quotaRemaining && batchResult.quotaRemaining < 50) {
      delay *= 3;
    }
    
    // Increase delay if errors occurred
    if (batchResult.errors.length > 0) {
      delay *= 2;
    }
    
    // Decrease delay during optimal hours
    const currentHour = new Date().getHours();
    if (currentHour >= 9 && currentHour <= 11) {
      delay *= 0.7;
    }
    
    return Math.min(delay, 60000); // Max 1 minute
  },
  
  /**
   * Generate optimization insights from batch results
   */
  generateOptimizationInsights: function(batchResults) {
    const insights = [];
    
    // Calculate success rates
    const totalProcessed = batchResults.reduce((sum, b) => sum + b.processed, 0);
    const totalErrors = batchResults.reduce((sum, b) => sum + b.errors.length, 0);
    const successRate = totalProcessed > 0 ? 
      ((totalProcessed - totalErrors) / totalProcessed * 100).toFixed(1) : 0;
    
    // Performance insights
    if (successRate < 90) {
      insights.push({
        type: 'performance',
        message: `Success rate is ${successRate}%. Consider reviewing error patterns.`,
        severity: 'warning'
      });
    }
    
    // Timing insights
    const avgDuration = batchResults.reduce((sum, b) => sum + (b.duration || 0), 0) / batchResults.length;
    if (avgDuration > 30) {
      insights.push({
        type: 'timing',
        message: `Average batch processing time is ${avgDuration.toFixed(1)}s. Consider smaller batches.`,
        severity: 'info'
      });
    }
    
    // Capacity insights
    const emailBatches = batchResults.filter(b => b.type === 'email');
    if (emailBatches.length > 0) {
      const lastQuota = emailBatches[emailBatches.length - 1].quotaRemaining;
      if (lastQuota < 100) {
        insights.push({
          type: 'capacity',
          message: `Gmail quota low (${lastQuota} remaining). Schedule for tomorrow.`,
          severity: 'warning'
        });
      }
    }
    
    return insights;
  },
  
  /**
   * Get execution time remaining
   */
  getExecutionTimeRemaining: function() {
    // Google Apps Script has 6-minute execution limit
    // This is a simplified estimation
    return 300; // 5 minutes in seconds
  },
  
  /**
   * Estimate memory usage
   */
  estimateMemoryUsage: function() {
    // Simplified memory estimation
    return {
      used: 50, // MB
      available: 150, // MB
      percentage: 25
    };
  },
  
  /**
   * Get PhantomBuster capacity
   */
  getPhantomBusterCapacity: function() {
    // Check PhantomBuster limits
    return {
      dailyLimit: 500,
      used: 0, // Would need to track this
      remaining: 500
    };
  },
  
  /**
   * Estimate processing time for batch
   */
  estimateProcessingTime: function(type, size) {
    const baseTime = {
      email: 0.5, // seconds per email
      linkedinConnect: 1, // seconds per connection
      linkedinMessage: 1.5 // seconds per message
    };
    
    return (baseTime[type] || 1) * size;
  },
  
  /**
   * Optimize batch size based on performance
   */
  optimizeBatchSize: function(type, currentSize, performance) {
    let optimalSize = currentSize;
    
    // Adjust based on error rate
    if (performance.errorRate > 0.1) {
      optimalSize = Math.floor(currentSize * 0.7);
    } else if (performance.errorRate < 0.02) {
      optimalSize = Math.floor(currentSize * 1.2);
    }
    
    // Apply limits
    const limits = {
      email: CAMPAIGN_LIMITS.MAX_BATCH_SIZE,
      linkedinConnect: 50,
      linkedinMessage: 25
    };
    
    return Math.min(optimalSize, limits[type] || currentSize);
  }
};

// Legacy function support
function runSmartBatch() {
  return SmartBatch.processOptimalBatches();
}