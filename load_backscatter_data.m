%% MATLAB Backscatter Data Analysis & Publication Plotting Script
% Loads snapshot datasets exported by the Native Backscatter SDR Acquisition GUI
% and generates academic publication-quality figures.

clear; close all; clc;

%% 1. Locate and Load Dataset
this_dir = fileparts(mfilename('fullpath'));
candidates = {
    fullfile(this_dir, 'software', 'output', 'snapshots'), ...
    fullfile(this_dir, 'ant test', '03_sdr_software', 'output', 'snapshots'), ...
    fullfile(this_dir, '03_sdr_software', 'output', 'snapshots'), ...
    fullfile(this_dir, 'output', 'snapshots'), ...
    fullfile(this_dir, 'ant test', 'sdr_pipeline', 'output', 'snapshots'), ...
    fullfile(this_dir, 'sdr_pipeline', 'output', 'snapshots')
};

snapshots_dir = '';
for k = 1:length(candidates)
    if exist(candidates{k}, 'dir')
        snapshots_dir = candidates{k};
        break;
    end
end

if isempty(snapshots_dir)
    error('Snapshot folder not found. Please click "EXPORT SNAPSHOT" in the Backscatter GUI first.');
end

mat_files = dir(fullfile(snapshots_dir, '*.mat'));
if isempty(mat_files)
    error('No .mat snapshot files found in %s. Please click "EXPORT SNAPSHOT" in the GUI first.', snapshots_dir);
end

% Select the latest snapshot by date
[~, idx] = max([mat_files.datenum]);
target_file = fullfile(mat_files(idx).folder, mat_files(idx).name);
fprintf('Loading latest backscatter snapshot: %s\n', mat_files(idx).name);

data = load(target_file);

%% 2. Extract Signal & Parameters
iq = data.iq_samples(:);
Fs = double(data.sample_rate);
fc = double(data.carrier_freq_hz);
rx_gain = double(data.rx_gain_db);
tx_gain = double(data.tx_gain_db);
carrier_mode = char(data.carrier_mode);
state_label = char(data.state_label);

N = length(iq);
t = (0:N-1)' / Fs;

% Instantaneous and moving average power (dBFS)
inst_power = abs(iq).^2;
win = max(1, round(Fs * 0.005)); % 5 ms window
power_ma = movmean(inst_power, win);
power_dbfs = 10 * log10(max(power_ma, 1e-12));

fprintf('\n=== Measurement Summary ===\n');
fprintf('  Carrier Frequency : %.3f MHz\n', fc / 1e6);
fprintf('  Sample Rate       : %.2f MS/s\n', Fs / 1e6);
fprintf('  RX Gain           : %.1f dB\n', rx_gain);
fprintf('  TX Gain           : %.1f dB\n', tx_gain);
fprintf('  Active State      : %s\n', state_label);
fprintf('  Sample Count      : %d (%.3f seconds)\n', N, N / Fs);

%% 3. Generate Publication Plots
figure('Name', 'Passive Backscatter Tag Analysis', 'Position', [100, 100, 1100, 750], 'Color', 'w');

% Subplot 1: Time-Domain Power Strip Chart
subplot(2, 2, [1, 2]);
plot(t * 1e3, power_dbfs, 'Color', [0, 0.45, 0.74], 'LineWidth', 1.5);
grid on;
title(sprintf('Time-Domain Received Power: P_{rx}(t) @ f_c = %.1f MHz (Mode: %s)', fc / 1e6, carrier_mode), 'FontSize', 12, 'FontWeight', 'bold');
xlabel('Time (ms)', 'FontSize', 11);
ylabel('Received Power (dBFS)', 'FontSize', 11);
ylim([min(power_dbfs)-5, max(power_dbfs)+5]);

% Subplot 2: Complex I/Q Constellation Phase Plane
subplot(2, 2, 3);
decimate_factor = max(1, round(N / 2000));
scatter(real(iq(1:decimate_factor:end)), imag(iq(1:decimate_factor:end)), 12, [0.85, 0.33, 0.1], 'filled', 'MarkerFaceAlpha', 0.5);
hold on;
plot(0, 0, 'k+', 'MarkerSize', 10, 'LineWidth', 1.5);
grid on; axis equal;
title('Complex I/Q Phase Plane Trajectory', 'FontSize', 12, 'FontWeight', 'bold');
xlabel('In-Phase (I)', 'FontSize', 11);
ylabel('Quadrature (Q)', 'FontSize', 11);

% Subplot 3: Power Spectral Density (PSD)
subplot(2, 2, 4);
nfft = 2048;
[pxx, f] = pwelch(iq, hamming(nfft), round(nfft/2), nfft, Fs, 'centered');
plot(f / 1e6, 10 * log10(pxx), 'Color', [0.47, 0.67, 0.19], 'LineWidth', 1.5);
grid on;
title('RF Power Spectral Density (PSD)', 'FontSize', 12, 'FontWeight', 'bold');
xlabel('Frequency Offset (MHz)', 'FontSize', 11);
ylabel('PSD (dB/Hz)', 'FontSize', 11);

fprintf('\nPlots generated successfully. Ready for supervisor report.\n');
