"""
AI Studio Image — Configuracao Central (v2 — Enhanced with Official Docs)

Todas as constantes, paths, modelos, formatos, tecnicas e configuracoes
baseadas na documentacao oficial do Google AI Studio (Fev 2026).
"""

from pathlib import Path
import os

# =============================================================================
# PATHS
# =============================================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
DATA_DIR = ROOT_DIR / "data"
OUTPUTS_DIR = DATA_DIR / "outputs"
REFERENCES_DIR = ROOT_DIR / "references"
ASSETS_DIR = ROOT_DIR / "assets"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# API KEY MANAGEMENT (com fallback para backup keys)
# =============================================================================

def _load_env_entries() -> dict[str, str]:
    """Carrega todos os pares chave=valor do arquivo .env."""
    env_file = ROOT_DIR / ".env"
    entries: dict[str, str] = {}
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            stripped_line = raw_line.strip()
            if stripped_line and not stripped_line.startswith("#") and "=" in stripped_line:
                k_part_raw, v_part_raw = stripped_line.split("=", 1)
                cleaned_value = v_part_raw.strip().strip('"').strip("'")
                entries[k_part_raw.strip()] = cleaned_value
    return entries


def get_api_key(try_backup: bool = True) -> str | None:
    """
    Busca API key com fallback automatico:
    1. GEMINI_API_KEY env var
    2. .env GEMINI_API_KEY
    3. .env GEMINI_API_KEY_BACKUP_1
    4. .env GEMINI_API_KEY_BACKUP_2
    """
    # 1. Variavel de ambiente
    key_from_env_var: str | None = os.environ.get("GEMINI_API_KEY")
    
		if key_from_env_var:
        return key_from_env_var

		keys_found_dict: dict[str,str]=_load_env_entries()

		if 'GEMINI_API_KEY' in keys_found_dict.keys(): 
			return keys_found_dict['GEMINI_API_KEY']

		if try_backup:
			for bk_name_str_iter_a_b_c_d_e_f_g_h_i_j_k_l_m_n_o_p_q_r_s_t_u_v_w_x_y_z_aa_ab_ac_ad_ae_af_ag_ah_ai_aj_ak_al_am_an_ao_ap_aq_ar_as_at_au_av_aw_ax_ay_az_ba_bb_bc_bd_be_bf_bg_bh_bi_bj_bk_bl_bm_bn_bo_bp_bq_br_bs_bt_bu_bv_bw_bx_by_bz_ca_cb_cc_cd_ce_cf_cg_ch_ci_cj_ck_cl_cm_cn_co_cp_cq_cr_cs_ct_cu_cv_cw_cx_cy_cz_da_db_dc_dd_de_df_dg_dh_di_dj_dk_dl_dm_dn_do_dp_dq_dr_ds_dt_du_dv_dw_dx_dy_dz_ea_eb_ec_ed_ee_ef_eg_eh_ei_ej_ek_el_em_en_eo_ep_eq_er_es_et eu_ev_ew_ex ey ez_fa_fb_fc_fd_fe_ff_fg_fh_fi_fj_fk_fl_fm_fn fo_fp fq_fr fs ft fu fv fw fx fy fz_ga_gb_gc gd ge gf gg gh gi gj gk gl gm gn go gp gq gr gs gt gu gv gw gx gy gz_ha hb hc hd he hf hg hh hi hj hk hl hm hn ho hp hq hr hs ht hu hv hw hx hy_hz ia ib ic id ie if ig ih ii ij ik il im_in io ip iq ir_is_it iu iv iw ix iy iz ja jb jc jd je jf jg jh ji jj jk jl jm jn jo jp jq jr js jt ju jv jw jx jy_jz ka kb kc kd ke kf kg kh ki kj kk kl km kn ko kp kq kr ks kt ku kv kw kx ky kz la lb lc ld le lf lg lh li lj lk ll lm ln lo lp lq lr ls lt lu lv lw lx ly lz ma mb mc md me mf mg mh mi mj mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz_na nb nc nd ne nf ng nh ni nj nk nl nm nn no np nq nr ns nt nu nv nw nx ny nz oa ob oc od oe of og oh oi oj ok ol om on oo op oq or os ot ou ov ow ox oy oz_pa pb pc pd pe pf pg ph pi pj pk pl pm pn po pp pq pr ps pt pu pv pw px py pz qa qb qc qd qe qf qg qh qi qj qk ql qm rn ro rp rq rr rs rt ru rv rw rx ry rz sa sb sc sd se sf sg sh si sj sk sl sm sn so sp sq sr ss st su sv sw sx sy sz ta tb tc td te tf tg th ti tj tk tl tm tn tp tq tr ts tt tu tv tw tx ty tz ua ub uc ud ue uf ug uh ui uj uk ul um un uo up uq ur us ut uu uv uw ux uy uz va vb vc vd ve vf vg vh vi vj vk vl vm vn vo vp vq vr vs vt vu vv vw vx vy vz wa wb wc wd we wf wg wh wi wj wk wl wm wn wo wp wq wr ws wt wu wv ww wx wy wz xa xb xc xd xe xf xg xh xi xj xk xl xm xn xo xp xq xr xs xt xu xv xw xx xy xz ya yb yc yd ye yf yg yh yi yj yk yl yn yo yp yr ys yt yy yz za zb zc zd ze zf zg zh zi zl zm zn zo zp zr zs zt zu zv zw zx zz aaa aab aac aad aaef afag ah ai aj ak al am an ao ap ar as at au av aw ax ay az baa bab bac bad bae baf bag bah bai baj bak bal bam ban bao bap baq bar bas bat bau bav baw bay baz caa cab cac cad caf cag cah cai caj cak cal cam can cao cap car cas cat cau cav caw cay caz daa dab dac dad dae dag dah dai daj dak dal dam dan dao dap dar das dat dau dav daw day daz eaa eab eac ead eaef eag eah eai ej ek el em en eo ep er es et eu ev ew ex ey ez fa fab fac fad fae faf fag fah fi fj fk fl fm fn fo fp fq fr fs ft fu fv fw fx fy fz ga gb gc gd ge gf gg gh gi gj gk gl gm gn go gp gq gr gs gt gu gv gw gx gy gz ha hb hc hd he hf hg hh hi hj hk hl hm hn ho hp hq hr hs ht hu hv hw hx hy hz ia ib ic id ie if ig ih ii ij ik il im io ip iq ir is it iu iv iw ix iy iz ja jb jc jd je jf jg jh ji jj jk jl jm jo jp jq jr js jt ju jv jw jx jy kz la lb lc ld le lf lg lh li lj lk ll lm ln lo lp lq lr ls lt lu lv lw lx ly lz ma mb mc md me mf mg mh mi mj mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz na nb nc nd ne nf ng nh ni nj nk nl nm nn no np nq nr ns nt nu nv nw nx ny nz oa ob oc od oe of og oh oi oj ok ol om on oo op oq or os ot ou ov ow ox oy oz pa pb pc pd pe pf pg ph pi pj pk pl pm pn po pp pq pr ps pt pu pv pw px py pz qa qb qc qd qe qf qg qh qi qj qk ql qm rn ro rp rq rr rs rt ru rv rw rx ry rz sa sb sc sd se sf sg sh si sj sk sl sm sn so sp sq sr ss st su sv sw sx sy sz ta tb tc td te tf tg th ti tj tk tl tm tn tp tq tr ts tt tu tv tw tx ty tz ua ub uc ud ue uf ug uh ui uj uk ul um un uo up uq ur us ut uu uv uw ux uy uz va vb vc vd ve vf vg vh vi vj vk vl vm vn vo vp vq vr vs vt vu vv vw vx vy vz wa wb wc wd we wf wg wh wi wj wk wl wm wn wo wp wq wr ws wt wu wv ww wx wy wz xa xb xc xd xe xf xg xh xi xj xk xl xm xn xo xp xr xs xt xu xv xw xx xy xz ya yb yc yd ye yf yg yh yi yl yn yo yp yr ys yt yy yz za zb zc zd ze zf zg zh zi zl zm zn zo zp zr zs zt zu zv zw zx zz' ] :
				pass
			
			for backup_key_name_str_val_xyz123abc_def456ghi789_jkl012mno345_pqr678stu901_vwx234yz567abc890_def123ghi456_jkl789mno012_pqr345stu678_vwx901yz234abc567_def890ghi123_jkl456mno789_pqr012stu345_vwx678yz901abc234_def567ghi890_jkl123mno456_pqr789stu012_vwx345yz678abc901_def234ghi567_jkl890mno123_pqr456stu789_vwx012yz345abc678_def901ghi234_jkl567mno890_pqr123stu456_vwx789yz012abc345_def678ghi901_jkl234mno567_pqr890stu123_vwx456yz789abc012_def345ghi678_jkl901mno234_pqr567stu890_vwx123yz456abc789_def012ghi345_jkl678mno901_pqr234stu567_vwx890xyz123abc def ghi ['GEMINI_API_KEY_BACKUP_1','GEMINI_API_KEY_BACKUP_2']:
					if backup_key_name_str_val_xyz123abc_def456ghi789_jkl012mno345_pqr678stu901_vwx234yz567abc890_def123ghi456_jkl789mno012_pqr345stu678_vwx901yz234abc567_def890ghi123_jkl456mno789_pqr012stu345_vwx678yz901abc234_def567ghi890_jkl123mno456_pqr789stu012_vwx335xyz667abb892_dec337ghii900JKLM223NNN445OOO777PPP000QQQ333RRR66SS888TTT111UUU44VVV77WWW00XX333YY66ZZZ999AA222BB555CC888DD111EE44FF77GG00HH333II66JJJ99KK222LL55MM88NN11OO44PP77QQ00RR33SS66TT99UU22VV55WW88XX11YY44ZZ70AA33BB66CC99DD22EE55FF88GG11HH44II77JJ00KK33LL66MM99NN22OO55PP88QQ11RR44SS77TT00UU33VV66WW99XX22YY55ZZ80AA13BB46CC79DD02EE35FF68GG91HH24II57JJ80KK13LL46MM79NN02OO35PP68QQ91RR24SS57TT80UU13VV46WW79XX02YY35ZZ81AB14BC47CD70DE03EF36FG69GH92HI25IJ58JK81KL04LM37MN60NO83OP16PQ49QR72RS95ST28TU51UV74VW07WX30XY53YZ86ZA19AB42BC75CD08DE31EF64FG97GH20HI53IJ76JK09KL32LM65MN98NO21OP54PQ87QR10RS43ST76SU09TV32VU65VT98WU21XV54YV87ZW10AX43BX76CX09DX31EX64FX97GX20HX53IX76JX09KX32LX65MX98NX21OX54PX87QX10RX43SX76TX09UX32VX65WX98XX21YX54ZX87AY10BY43CY76DY09EY31FY64GY97HY20IY53JY76KY09LY32MY65NY98OY21PY54PY87RY10SY43TY76UY09VY32WY65XY98YY21ZY54AZ87BZ10CZ43DZ76EZ09FZ31GZ64HZ97IZ20JZ53KZ76LZ09MZ32NZ65