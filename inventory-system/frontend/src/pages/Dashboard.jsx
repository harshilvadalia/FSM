import { useState } from 'react';
import BoxesTab from '../components/BoxesTab';
import ItemsTab from '../components/ItemsTab';
import SubCompartmentsTab from '../components/SubCompartmentsTab';
import TransactionsTab from '../components/TransactionsTab';
import OperationsTab from '../components/OperationsTab';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

function Dashboard() {
  const [activeTab, setActiveTab] = useState('boxes');

  const renderTabContent = () => {
    switch (activeTab) {
      case 'boxes':
        return <BoxesTab />;
      case 'items':
        return <ItemsTab />;
      case 'subcompartments':
        return <SubCompartmentsTab />;
      case 'transactions':
        return <TransactionsTab />;
      case 'operations':
        return <OperationsTab />;
      default:
        return <BoxesTab />;
    }
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Inventory Management System</h1>
      </header>
      
      <div className="tabs">
        <button 
          className={activeTab === 'boxes' ? 'active' : ''} 
          onClick={() => setActiveTab('boxes')}
        >
          Boxes
        </button>
        <button 
          className={activeTab === 'items' ? 'active' : ''} 
          onClick={() => setActiveTab('items')}
        >
          Items
        </button>
        <button 
          className={activeTab === 'subcompartments' ? 'active' : ''} 
          onClick={() => setActiveTab('subcompartments')}
        >
          Sub Compartments
        </button>
        <button 
          className={activeTab === 'transactions' ? 'active' : ''} 
          onClick={() => setActiveTab('transactions')}
        >
          Transactions
        </button>
        <button 
          className={activeTab === 'operations' ? 'active' : ''} 
          onClick={() => setActiveTab('operations')}
        >
          Operations
        </button>
      </div>
      
      <div className="tab-content">
        {renderTabContent()}
      </div>
      
      <ToastContainer position="bottom-right" />
    </div>
  );
}

export default Dashboard;
