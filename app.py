import streamlit as st
import numpy as np
import pandas as pd
import altair as alt
import scipy.constants as constants
from scipy.integrate import simps, quad
from scipy.interpolate import splrep, splint
from scipy.optimize import fmin

st.write("# Shockley-Queisser Limit Calculator")

with st.beta_expander("Written by:"):
    st.write("""
    Original code was written by **Dr. Mark Ziffer** as a 
    graduate student in the **Ginger lab at the University of
    Washington**.

    Modified and deployed to web by **Sarthak Jariwala** (jariwala@uw.edu),
     graduate student in the Ginger lab.

    Code available at https://github.com/SarthakJariwala/Shockley-Queisser-Web-App
    """)

h = constants.physical_constants['Planck constant'][0] # units of J*s
h_ev = constants.physical_constants['Planck constant in eV s'][0]
c_nm = (constants.physical_constants['speed of light in vacuum'][0]) * 1e9
c = (constants.physical_constants['speed of light in vacuum'][0])

e_charge = constants.physical_constants['elementary charge'][0] 
kb_ev = constants.physical_constants['Boltzmann constant in eV/K'][0]

bandgap_array_min = 0.5 # in eV
bandgap_array_max = 3 # in eV
num_points_bandgap_array = 30

@st.cache
def load_data(filename=r"ASTMG173.csv"):

    #First convert AM1.5 spectrum from W/m^2/nm to W/m^2/ev
    astmg173 = np.loadtxt(filename, delimiter=",", skiprows=2)
    am15_wav = np.copy(astmg173[:,0]) #AM1.5 wavelength axis in nm
    am15 = np.copy(astmg173[:,1]) #AM1.5 in units of W/m^2/nm = J/s*m^2/nm

    #Integrate over nm to check that total power density = 1000 W/m^2
    # total_power_nm = simps(am15, x = am15_wav)

    am15_ev = h_ev * (c_nm) / (am15_wav )
    am15_wats_ev = am15 * (h_ev * c_nm/ ((am15_ev) ** 2.0))

    am15_ev_flip = am15_ev[::-1] 
    am15_wats_ev_flip = am15_wats_ev[::-1]

    #Integrate over eV to check that total power density = 1000 W/m^2
    total_power_ev = simps(am15_wats_ev_flip, x = am15_ev_flip) 

    am15_photons_ev  = am15_wats_ev_flip / (am15_ev_flip * e_charge)

    am15_photons_nm = am15 / (am15_ev * e_charge)

    total_photonflux_ev = simps(am15_photons_ev, x = am15_ev_flip)

    total_photonflux_nm = simps(am15_photons_nm , x = am15_wav)

    total_photonflux_ev_splrep = splrep(am15_ev_flip, am15_photons_ev)

    emin = am15_ev_flip[0]
    emax = am15_ev_flip[len(am15_ev_flip) - 1]
    return total_power_ev, total_photonflux_ev_splrep, emin, emax


def calculate_SQ(Tcell=300., bandgap=1.63):

    bandgap_array = np.linspace(bandgap_array_min, bandgap_array_max, num_points_bandgap_array)
    
    total_power_ev, total_photonflux_ev_splrep, emin, emax = load_data()
    
    def solar_photons_above_gap(Egap): #units of photons / sec *m^2
        return splint(Egap, emax,total_photonflux_ev_splrep) 

    def RR0(Egap):
        integrand = lambda eV : eV ** 2.0 / (np.exp(eV / (kb_ev * Tcell)) - 1)
        integral = quad(integrand, Egap, emax, full_output=1)[0]
        return ((2.0 * np.pi / ((c ** 2.0) * (h_ev ** 3.0)))) * integral

    def current_density(V, Egap): #to get from units of amps / m^2 to mA/ cm^2 ---multiply by 1000 to convert to mA ---- multiply by (0.01 ^2) to convert to cm^2
        cur_dens =  e_charge * (solar_photons_above_gap(Egap) - RR0(Egap) * np.exp( V / (kb_ev * Tcell)))    
        return cur_dens * 1000 * (0.01 ** 2.0)
    
    def JSC(Egap): 
        return current_density(0, Egap) 

    def VOC(Egap):
        return (kb_ev * Tcell) * np.log(solar_photons_above_gap(Egap) / RR0(Egap))

    def fmax(func_to_maximize, initial_guess=0):
        """return the x that maximizes func_to_maximize(x)"""
        func_to_minimize = lambda x : -func_to_maximize(x)
        return fmin(func_to_minimize, initial_guess, disp=False)[0]    

    def V_mpp_Jmpp_maxpower_maxeff_ff(Egap):

        vmpp = fmax(lambda V : V * current_density(V, Egap))    
        jmpp = current_density(vmpp, Egap)

        maxpower =  vmpp * jmpp
        max_eff = maxpower / (total_power_ev * 1000 * (0.01 ** 2.0))
        jsc_return =  JSC(Egap)
        voc_return = VOC(Egap)
        ff = maxpower / (jsc_return * voc_return)    
        return [vmpp, jmpp, maxpower, max_eff, ff, jsc_return, voc_return]


    maxpcemeta = V_mpp_Jmpp_maxpower_maxeff_ff(bandgap)

#     print('For Bandgap = %.3f eV, TCell = %.3f K:\nJSC = %.3f mA/cm^2\nVOC = %.3f V\nFF = %.3f\nPCE = %.3f' % (bandgap, Tcell, maxpcemeta[5], maxpcemeta[6],maxpcemeta[4], maxpcemeta[3] * 100)))


    pce_array = np.empty_like(bandgap_array)
    ff_array = np.empty_like(bandgap_array)
    voc_array = np.empty_like(bandgap_array)
    jsc_array = np.empty_like(bandgap_array)
    
    for i in range(len(bandgap_array)):
        metadata = V_mpp_Jmpp_maxpower_maxeff_ff(bandgap_array[i])
        pce_array[i] = metadata[3] 
        ff_array[i] = metadata[4]
        voc_array[i] = metadata[6]
        jsc_array[i] = metadata[5]

    out_array = np.array((bandgap_array,100*pce_array,ff_array, voc_array,jsc_array)).T
    
    df = pd.DataFrame(out_array, columns=["Bandgap (eV)", "PCE (%)", "Fill Factor", "Voc (V)", "Jsc (mA/cm2)"])


    def JV_curve(Egap):
        volt_array = np.linspace(0, VOC(Egap), 200)
        j_array = np.empty_like(volt_array)
        for i in range(len(volt_array)):
            j_array[i] = current_density(volt_array[i], Egap)
        return [volt_array, j_array]


    jv_meta = JV_curve(bandgap)
    
    df_2 = pd.DataFrame(np.array([jv_meta[0], -jv_meta[1]]).T, columns=["Voltage (V)", "Current Density (mA/cm2)"])

    return df, df_2, maxpcemeta

st.write("### Select the temperature (K) and bandgap (eV) of interest")

t_col, b_col = st.beta_columns(2)
cell_temperature = t_col.slider("Temperature (K)", min_value=100, max_value=500, value=300)
bandgap = b_col.slider("Bandgap (eV)", min_value=0.5, max_value=3., value=1.63)

df, df_2, maxpcemeta = calculate_SQ(Tcell=cell_temperature, bandgap=bandgap)

st.write("## Device Metrics")
st.write(f"J$_{'s'}$$_{'c'}$ = {maxpcemeta[5]:.2f} mA/cm$^{2}$")
st.write(f"V$_{'o'}$$_{'c'}$ = {maxpcemeta[6]:.2f} V")
st.write(f"FF = {maxpcemeta[4]:.2f}")
st.write(f"PCE = {maxpcemeta[3] * 100:.2f} %")

st.write("## Plots")

c = alt.Chart(df_2).mark_line(point=True).encode(
    x="Voltage (V)", y="Current Density (mA/cm2)"
)
with st.beta_expander("J-V Curve"):
    st.altair_chart(c, use_container_width=True)

c_pce = alt.Chart(df).mark_line(point=True).encode(
    x="Bandgap (eV)", y="PCE (%)"
)

c_voc = alt.Chart(df).mark_line(point=True).encode(
    x="Bandgap (eV)", y="Voc (V)"
)

c_jsc = alt.Chart(df).mark_line(point=True).encode(
    x="Bandgap (eV)", y="Jsc (mA/cm2)"
)

c_ff = alt.Chart(df).mark_line(point=True).encode(
    x="Bandgap (eV)", y="Fill Factor"
)

with st.beta_expander("Device metrics as a function of bandgap"):
    col_00, col_01 = st.beta_columns(2)
    col_10, col_11 = st.beta_columns(2)

    col_00.altair_chart(c_pce, use_container_width=True)
    col_01.altair_chart(c_voc, use_container_width=True)
    col_10.altair_chart(c_jsc, use_container_width=True)
    col_11.altair_chart(c_ff, use_container_width=True)
