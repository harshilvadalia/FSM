const db = require('../config/db');

class TransactionModel {
  static async getAllTransactions(sortOption = 'id_asc', limit = 100) {
    try {
      let query = `
        SELECT t.tran_id, i.name as item_name, t.subcom_place, t.action, t.time
        FROM Transactions t
        LEFT JOIN Items i ON t.item_id = i.item_id
      `;
      
      // Apply sorting based on option
      switch (sortOption) {
        case 'newest_first':
          query += ` ORDER BY t.time DESC`;
          break;
        case 'added_only':
          query += ` WHERE t.action = 'added' ORDER BY t.tran_id ASC`;
          break;
        case 'retrieved_only':
          query += ` WHERE t.action = 'retrieved' ORDER BY t.tran_id ASC`;
          break;
        default: // id_asc
          query += ` ORDER BY t.tran_id ASC`;
      }
      
      query += ` LIMIT ${limit}`;
      
      const [rows] = await db.query(query);
      return rows;
    } catch (error) {
      throw new Error(`Error fetching transactions: ${error.message}`);
    }
  }

  static async getTransactionById(tranId) {
    try {
      const [rows] = await db.query(`
        SELECT t.tran_id, i.name as item_name, t.subcom_place, t.action, t.time
        FROM Transactions t
        LEFT JOIN Items i ON t.item_id = i.item_id
        WHERE t.tran_id = ?
      `, [tranId]);
      return rows[0];
    } catch (error) {
      throw new Error(`Error fetching transaction by ID: ${error.message}`);
    }
  }

  static async getTransactionsByItemId(itemId) {
    try {
      const [rows] = await db.query(`
        SELECT t.tran_id, i.name as item_name, t.subcom_place, t.action, t.time
        FROM Transactions t
        LEFT JOIN Items i ON t.item_id = i.item_id
        WHERE t.item_id = ?
        ORDER BY t.time DESC
      `, [itemId]);
      return rows;
    } catch (error) {
      throw new Error(`Error fetching transactions by item ID: ${error.message}`);
    }
  }
}

module.exports = TransactionModel;
