import React, { useState, useCallback } from 'react';
import { HiOutlinePlus, HiOutlineX, HiOutlineCheck, HiOutlineExclamation } from 'react-icons/hi';
import { toast } from 'react-hot-toast';

export default function MedicineManager() {
  const [medicines, setMedicines] = useState([]);
  const [patientName, setPatientName] = useState('');
  const [currentMedicine, setCurrentMedicine] = useState({
    name: '',
    dosage: '',
    frequency: '',
    duration: '',
    purpose: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);

  // Handle form input changes
  const handleMedicineChange = useCallback((field, value) => {
    setCurrentMedicine(prev => ({
      ...prev,
      [field]: value
    }));
  }, []);

  // Add medicine to list
  const handleAddMedicine = useCallback(() => {
    if (!currentMedicine.name.trim()) {
      toast.error('Medicine name is required');
      return;
    }

    setMedicines(prev => [...prev, {
      ...currentMedicine,
      id: Date.now() // Unique ID for removal
    }]);

    // Reset form
    setCurrentMedicine({
      name: '',
      dosage: '',
      frequency: '',
      duration: '',
      purpose: '',
    });

    toast.success('Medicine added');
  }, [currentMedicine]);

  // Remove medicine from list
  const handleRemoveMedicine = useCallback((id) => {
    setMedicines(prev => prev.filter(m => m.id !== id));
    toast.success('Medicine removed');
  }, []);

  // Submit to backend (save to MongoDB + Zoho CRM)
  const handleSubmit = async () => {
    if (!patientName.trim()) {
      toast.error('Patient name is required');
      return;
    }

    if (medicines.length === 0) {
      toast.error('Add at least one medicine');
      return;
    }

    setIsLoading(true);

    try {
      // Format medicines for backend
      const medicineList = medicines.map(m => ({
        name: m.name,
        dosage: m.dosage || 'As prescribed',
        frequency: m.frequency || 'Regular',
        duration: m.duration || 'Ongoing',
        purpose: m.purpose || 'Medical treatment'
      }));

      // Create voice-like request
      const voiceInput = `${patientName} prescribed: ${medicineList.map(m => `${m.name} ${m.dosage}`).join(', ')}`;

      // Send to voice endpoint (handles extraction + DB + CRM)
      const response = await fetch('http://localhost:8000/api/voice/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          voice_input: voiceInput,
          timestamp: new Date().toISOString()
        })
      });

      if (!response.ok) {
        throw new Error('Failed to save medicines');
      }

      const data = await response.json();

      if (data.success) {
        toast.success(`✅ ${medicines.length} medicine(s) saved for ${patientName}`);
        toast.success('✅ Synced to Zoho CRM');

        // Reset form
        setMedicines([]);
        setPatientName('');
        setShowForm(false);
      } else {
        toast.error(data.message || 'Failed to save medicines');
      }
    } catch (error) {
      console.error('Error saving medicines:', error);
      toast.error('Error: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="medicine-manager p-4 bg-slate-900/50 rounded-lg border border-slate-700 max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-gold flex items-center gap-2">
          💊 Medicine Manager
        </h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="p-2 hover:bg-slate-700 rounded-lg transition"
          title={showForm ? 'Hide form' : 'Show form'}
        >
          <HiOutlinePlus size={20} />
        </button>
      </div>

      {/* Patient Name Input */}
      {showForm && (
        <div className="space-y-4 mb-4">
          <input
            type="text"
            placeholder="Enter patient name..."
            value={patientName}
            onChange={(e) => setPatientName(e.target.value)}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-gold"
          />

          {/* Medicine Form */}
          <div className="bg-slate-800/50 p-3 rounded border border-slate-700 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Medicine name *"
                value={currentMedicine.name}
                onChange={(e) => handleMedicineChange('name', e.target.value)}
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-gold col-span-2"
              />
              <input
                type="text"
                placeholder="Dosage (e.g., 650mg)"
                value={currentMedicine.dosage}
                onChange={(e) => handleMedicineChange('dosage', e.target.value)}
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-gold"
              />
              <input
                type="text"
                placeholder="Frequency (e.g., twice daily)"
                value={currentMedicine.frequency}
                onChange={(e) => handleMedicineChange('frequency', e.target.value)}
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-gold"
              />
              <input
                type="text"
                placeholder="Duration (e.g., 5 days)"
                value={currentMedicine.duration}
                onChange={(e) => handleMedicineChange('duration', e.target.value)}
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-gold col-span-2"
              />
              <input
                type="text"
                placeholder="Purpose (e.g., fever, pain)"
                value={currentMedicine.purpose}
                onChange={(e) => handleMedicineChange('purpose', e.target.value)}
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-gold col-span-2"
              />
            </div>

            <button
              onClick={handleAddMedicine}
              className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition flex items-center justify-center gap-2"
            >
              <HiOutlinePlus size={18} /> Add Medicine
            </button>
          </div>
        </div>
      )}

      {/* Medicines List */}
      <div className="space-y-2 mb-4 max-h-64 overflow-y-auto">
        {medicines.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-4">
            No medicines added yet
          </p>
        ) : (
          medicines.map((med) => (
            <div
              key={med.id}
              className="bg-slate-800 p-3 rounded border border-slate-600 flex items-start justify-between gap-2 hover:border-gold transition"
            >
              <div className="flex-1">
                <div className="font-semibold text-white flex items-center gap-2">
                  <span className="text-gold">💊</span>
                  {med.name}
                </div>
                <div className="text-xs text-slate-400 mt-1 space-y-0.5">
                  {med.dosage && <p>📏 {med.dosage}</p>}
                  {med.frequency && <p>⏰ {med.frequency}</p>}
                  {med.duration && <p>📅 {med.duration}</p>}
                  {med.purpose && <p>🎯 {med.purpose}</p>}
                </div>
              </div>
              <button
                onClick={() => handleRemoveMedicine(med.id)}
                className="p-2 hover:bg-red-500/20 text-red-400 rounded transition flex-shrink-0"
                title="Remove"
              >
                <HiOutlineX size={18} />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Summary & Submit */}
      {medicines.length > 0 && (
        <div className="bg-slate-800/50 p-3 rounded border border-slate-700 mb-4">
          <p className="text-sm text-slate-300 mb-2">
            💾 Ready to save <span className="font-bold text-gold">{medicines.length}</span> medicine(s) 
            for <span className="font-bold text-gold">{patientName || 'patient'}</span>
          </p>
          <button
            onClick={handleSubmit}
            disabled={isLoading}
            className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded font-medium transition flex items-center justify-center gap-2"
          >
            <HiOutlineCheck size={18} />
            {isLoading ? 'Saving...' : 'Save & Sync to CRM'}
          </button>
        </div>
      )}

      {/* Info */}
      <div className="text-xs text-slate-400 bg-slate-900/50 p-2 rounded border border-slate-700">
        <div className="flex gap-2">
          <HiOutlineExclamation size={14} className="flex-shrink-0 mt-0.5" />
          <div>
            ✅ Automatically stores in MongoDB<br />
            ✅ Syncs to Zoho CRM<br />
            ✅ Links to patient record
          </div>
        </div>
      </div>
    </div>
  );
}
