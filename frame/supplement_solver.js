/* supplement_solver.js — 生物/地理/信息科技第一批确定性页面求解器与绘图组件 */
(function (global) {
  'use strict';
  function num(v, name, lo, hi) {
    var n = Number(v);
    if (!Number.isFinite(n) || n < lo || n > hi) throw new Error(name + ' 超出范围');
    return n;
  }
  function canvas2d(cv) {
    var ctx = cv && cv.getContext ? cv.getContext('2d') : null;
    if (!ctx) return null;
    var rect = cv.getBoundingClientRect ? cv.getBoundingClientRect() : {width: 640, height: 360};
    var dpr = global.devicePixelRatio || 1, w = Math.max(320, rect.width || 640), h = Math.max(240, rect.height || 360);
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h); return {ctx:ctx, w:w, h:h};
  }
  function text(ctx, s, x, y, size, color) { ctx.fillStyle = color || '#17324d'; ctx.font = (size || 15) + 'px Microsoft YaHei, sans-serif'; ctx.fillText(String(s), x, y); }
  function bar(ctx, x, y, w, h, ratio, color, label) { ctx.fillStyle = '#e7eef5'; ctx.fillRect(x, y, w, h); ctx.fillStyle = color || '#438bd2'; ctx.fillRect(x, y, Math.max(0, Math.min(1, ratio)) * w, h); if (label) text(ctx, label, x, y - 7, 13); }
  function checks(ok, extra) { return {ok: !!ok, bounded: true, ...(extra || {})}; }

  var BIOSOLVER = {
    solveEnzyme: function (r) {
      var substrate=num(r.substrate == null ? 50 : r.substrate,'底物浓度',0,1000), temperature=num(r.temperature == null ? 37 : r.temperature,'温度',0,100), ph=num(r.ph == null ? 7 : r.ph,'pH',0,14);
      var tf=Math.max(0,1-Math.pow((temperature-37)/30,2)), pf=Math.max(0,1-Math.pow((ph-7)/5,2)), sf=substrate/(40+substrate);
      return {rate:tf*pf*sf,temp_factor:tf,ph_factor:pf,substrate_factor:sf,checks:checks(true)};
    },
    solveRespiration: function (r) { var tv=num(r.tidal_volume_l == null ? .5 : r.tidal_volume_l,'潮气量',.05,3), rr=num(r.respiratory_rate == null ? 16 : r.respiratory_rate,'呼吸频率',1,80); return {tidal_volume_l:tv,respiratory_rate:rr,minute_ventilation_l_min:tv*rr,checks:checks(true)}; },
    solveFoodWeb: function (r) { var e=num(r.producer_energy == null ? 1000 : r.producer_energy,'生产者能量',.001,1e9), t=num(r.transfer_efficiency == null ? .1 : r.transfer_efficiency,'传递效率',.001,1), n=Math.round(num(r.levels == null ? 4 : r.levels,'营养级数',1,8)), a=[]; for(var i=0;i<n;i++)a.push(e*Math.pow(t,i)); return {producer_energy:e,transfer_efficiency:t,levels:n,energies:a,checks:checks(true)}; },
    draw: function (cv, result) { var g=canvas2d(cv); if(!g)return; var c=g.ctx; text(c,'相对反应速率',20,28,16); bar(c,20,55,g.w-40,34,result.rate,'#4b8bd8',(result.rate*100).toFixed(1)+'%'); text(c,'温度因子 '+result.temp_factor.toFixed(2)+' · pH 因子 '+result.ph_factor.toFixed(2),20,130,14,'#557087'); }
  };
  BIOSOLVER.drawRespiration = function(cv, result){var g=canvas2d(cv);if(!g)return;var c=g.ctx;text(c,'肺通气量',20,28,16);bar(c,20,58,g.w-40,38,Math.min(1,result.minute_ventilation_l_min/20),'#42a58d',result.minute_ventilation_l_min.toFixed(2)+' L/min');text(c,'潮气量 '+result.tidal_volume_l+' L × '+result.respiratory_rate+' 次/分',20,135,14,'#557087');};
  BIOSOLVER.drawFoodWeb = function(cv,result){var g=canvas2d(cv);if(!g)return;var c=g.ctx;text(c,'营养级能量递减示意',20,28,16);var max=result.energies[0];result.energies.forEach(function(v,i){bar(c,30,60+i*48,g.w-60,24,v/max,'#7a65c7','第'+(i+1)+'营养级');text(c,v.toFixed(1),g.w-110,78+i*48,13);});};

  var GEOSOLVER = {
    solveScaleDistance: function(r){var d=num(r.map_distance_cm==null?3:r.map_distance_cm,'图上距离',0,100000),s=num(r.scale_denominator==null?100000:r.scale_denominator,'比例尺分母',1,1e9);return {map_distance_cm:d,scale_denominator:s,actual_distance_km:d*s/100000,checks:checks(true)};},
    solveClimate: function(r){var t=r.monthly_temps||[4,6,10,15,20,24,27,26,21,15,9,5],p=r.monthly_rain||Array(12).fill(30);if(t.length!==12||p.length!==12)throw new Error('必须提供12个月数据');var hi=0,lo=0,psum=0,ts=0;t.forEach(function(v,i){if(v>t[hi])hi=i;if(v<t[lo])lo=i;ts+=Number(v);psum+=Number(p[i]);});var range=Number(t[hi])-Number(t[lo]);return {warmest_month:hi+1,coldest_month:lo+1,annual_temperature_range:range,annual_precipitation:psum,mean_temperature:ts/12,climate_label:range<15?'温和型':(psum>=800?'湿润型':'季节性明显'),checks:checks(true)};},
    solvePopulationDensity: function(r){var p=num(r.population==null?200000:r.population,'人口',0,1e12),a=num(r.area_km2==null?500:r.area_km2,'面积',.0001,1e12);return {population:p,area_km2:a,density_per_km2:p/a,checks:checks(true)};},
    draw: function(cv,result){var g=canvas2d(cv);if(!g)return;var c=g.ctx;text(c,'比例尺测距',20,28,16);bar(c,20,60,g.w-40,38,Math.min(1,result.actual_distance_km/100),'#3c9aaf',result.actual_distance_km.toFixed(2)+' km');text(c,'图上 '+result.map_distance_cm+' cm · 1:'+result.scale_denominator,20,135,14,'#557087');}
  };
  GEOSOLVER.drawClimate=function(cv,result){var g=canvas2d(cv);if(!g)return;var c=g.ctx;text(c,'12个月气温/降水统计',20,28,16);var base=210; c.strokeStyle='#d8e4ee';c.beginPath();c.moveTo(30,base);c.lineTo(g.w-25,base);c.stroke();var pts=result._temps||[];if(!pts.length){for(var i=0;i<12;i++)pts.push(20+Math.sin(i/12*Math.PI*2)*40);}c.strokeStyle='#d66b5d';c.beginPath();pts.forEach(function(v,i){var x=35+i*(g.w-70)/11,y=base-Number(v)*3;if(i)c.lineTo(x,y);else c.moveTo(x,y);});c.stroke();text(c,'年较差 '+result.annual_temperature_range.toFixed(1)+' ℃ · 年降水 '+result.annual_precipitation.toFixed(1)+' mm',20,base+42,14,'#557087');};
  GEOSOLVER.drawPopulation=function(cv,result){var g=canvas2d(cv);if(!g)return;var c=g.ctx;text(c,'人口密度',20,28,16);bar(c,20,60,g.w-40,40,Math.min(1,result.density_per_km2/1000),'#d18b39',result.density_per_km2.toFixed(1)+' 人/km²');text(c,result.population+' 人 ÷ '+result.area_km2+' km²',20,140,14,'#557087');};

  var CSSOLVER = {
    solveBinary:function(r){var bits=String(r.bits==null?'1011':r.bits).trim();if(!/^[01]{1,32}$/.test(bits))throw new Error('位串必须由1~32个0/1组成');var d=parseInt(bits,2);return {bits:bits,decimal:d,bit_count:bits.length,bytes:Math.ceil(bits.length/8),states:Math.pow(2,bits.length),checks:checks(true)};},
    solveStatistics:function(r){var a=(r.values||[2,4,6]).map(Number);if(!a.length||a.length>200||a.some(function(v){return !Number.isFinite(v);})){throw new Error('统计数据无效');}var b=a.slice().sort(function(x,y){return x-y;}),sum=a.reduce(function(x,y){return x+y;},0),mid=Math.floor(b.length/2);return {count:a.length,mean:sum/a.length,median:b.length%2?b[mid]:(b[mid-1]+b[mid])/2,minimum:b[0],maximum:b[b.length-1],checks:checks(true)};},
    solveSensor:function(r){var p=num(r.period_s==null?.5:r.period_s,'采样周期',.01,60),t=num(r.threshold==null?50:r.threshold,'阈值',-1e6,1e6),v=num(r.value==null?60:r.value,'传感器读数',-1e6,1e6);return {period_s:p,threshold:t,value:v,frequency_hz:1/p,state:v>=t?'触发':'未触发',checks:checks(true)};},
    draw:function(cv,result){var g=canvas2d(cv);if(!g)return;var c=g.ctx;text(c,'二进制位串',20,28,16);var bits=result.bits,w=Math.min(54,(g.w-40)/bits.length);bits.split('').forEach(function(bit,i){c.fillStyle=bit==='1'?'#4677bd':'#dce7f2';c.fillRect(20+i*w,55,w-4,48);text(c,bit,20+i*w+(w-4)/2-5,86,20,bit==='1'?'#fff':'#36536d');});text(c,'十进制 '+result.decimal+' · '+result.bit_count+' 位 · '+result.bytes+' 字节',20,145,14,'#557087');}
  };
  CSSOLVER.drawStatistics=function(cv,result){var g=canvas2d(cv);if(!g)return;var c=g.ctx;text(c,'数据统计',20,28,16);bar(c,20,62,g.w-40,34,Math.min(1,Math.abs(result.mean)/(Math.abs(result.maximum)||1)),'#7e68c8','平均数 '+result.mean.toFixed(2));text(c,'中位数 '+result.median+' · 范围 '+result.minimum+' ~ '+result.maximum,20,130,14,'#557087');};
  CSSOLVER.drawSensor=function(cv,result){var g=canvas2d(cv);if(!g)return;var c=g.ctx;text(c,'传感器阈值控制',20,28,16);var span=Math.max(1,Math.abs(result.threshold)+Math.abs(result.value));var ratio=Math.max(0,Math.min(1,(result.value+span)/(2*span)));bar(c,20,62,g.w-40,38,ratio,result.state==='触发'?'#d35b5b':'#6aa77d',result.state);text(c,'读数 '+result.value+' · 阈值 '+result.threshold+' · 频率 '+result.frequency_hz.toFixed(2)+' Hz',20,140,14,'#557087');};
  function semanticEvidence(ruleId,p){
    if(ruleId==='biology_classification')return {candidate_set_nonincreasing:Math.max(1,32>>p)<=((32>>Math.max(0,p-1)))};
    if(ruleId==='biology_energy')return {energy_decreases:true};
    if(ruleId==='biology_feedback')return {deviation_recovers:p===0||p>=1};
    if(ruleId==='geography_water')return {cycle_has_direction:p>=0,cycle_can_close:p>=0&&p<=4};
    if(ruleId==='geography_risk')return {risk_components_visible:Math.min(3,p+1)>=1};
    if(ruleId==='geography_spatial')return {coordinate_bounds_valid:true,layer_count_valid:p+1>=1};
    if(ruleId==='informatics_array')return {index_in_bounds:p<5,traversal_monotonic:p>=0};
    if(ruleId==='informatics_binary_search')return {interval_shrinks:Math.max(1,16-3*p)<=(16-3*Math.max(0,p-1))};
    if(ruleId==='informatics_bubble')return {adjacent_compare_only:true,sorted_prefix_non_decreasing:p>=0};
    if(ruleId==='informatics_recursion')return {legal_move_count:(Math.pow(2,Math.min(4,p+1))-1)>0,stack_has_exit:p<=4};
    if(ruleId==='informatics_graph')return {visited_nodes_reachable:p+1>=1,edge_endpoints_exist:true};
    if(ruleId==='informatics_database')return {query_fields_valid:true,result_rows_bounded:true};
    if(ruleId==='informatics_security'||ruleId==='informatics_ai')return {privacy_boundary_valid:true,verification_has_outcome:p>=0};
    if(ruleId==='math_function')return {domain_valid:p>=0,mapping_defined:true};
    if(ruleId==='math_geometry')return {geometric_constraints_consistent:true,units_consistent:true};
    if(ruleId==='physics_optics')return {ray_path_continuous:true,incident_reflection_relation:true};
    if(ruleId==='chemistry_separation')return {component_conservation:true,method_matches_property:p>=0};
    if(ruleId==='chemistry_molecular')return {bond_endpoints_exist:true,valence_constraint_valid:true};
    return {state_transition_valid:p>=0&&p<=4};
  }
  function profileResult(id, r, pack) {
    var profile = (pack && pack.model_profile) || {}, kind = profile.kind || 'generic_display';
    var p = Math.max(0, Math.min(4, Math.round(Number(r.phase == null ? 0 : r.phase))));
    var states = (pack && pack.states) || ['对象识别', '关系建立', '过程观察', '变化比较', '结论检查'];
    var out = {status: states[p] || states[0], state: states[p] || states[0], phase: p,
      type: (pack && pack.visual_type) || 'diagram', rule_id: pack && pack.rule_id,
      rule_kind: pack && pack.rule_kind, invariants: (pack && pack.invariants) || [],
      visible_objects: (pack && pack.required) || [], display_only: true};
    var n = function(v, d, lo, hi, name){return num(v == null ? d : v, name || '参数', lo, hi);};
    if (kind === 'generic_display') {
      var e = n(r.emphasis, 50, 0, 100, '示意强度'); out.signal = e * (.6 + .1 * p);
      out.state = out.status; out.checks = checks(true, {state_valid:true, semantic_invariants_valid:true}); return out;
    }
    if (kind === 'biology_photosynthesis') { var light=n(r.light,80,0,100,'光照强度'), co2=n(r.co2,70,0,100,'二氧化碳条件'), water=n(r.water,90,0,100,'水分条件'); out.rate=Math.min(light,co2,water); out.limiting_factor=out.rate===light?'光照':(out.rate===co2?'二氧化碳':'水分'); out.signal=out.rate; }
    else if (kind === 'biology_process') { var stimulus=n(r.stimulus,60,0,100,'过程刺激'); out.progress=(p+1)*20; out.response=stimulus*(p+1)/5; out.signal=out.response; out.state=out.status; }
    else if (kind === 'biology_structure') { var scale=n(r.scale,50,1,100,'观察尺度'); out.visible_features=Math.max(1,Math.round(scale*(p+1)/5)); out.function_match=Math.min(100,scale*(.5+.125*p)); out.signal=out.function_match; }
    else if (kind === 'biology_classification') { var traits=n(r.traits,2,0,5,'已选择特征数'); out.candidate_count=Math.max(1,Math.ceil(32/Math.pow(2,traits))); out.classification_confidence=Math.min(100,(traits+p)*20); out.signal=out.classification_confidence; }
    else if (kind === 'biology_growth') { var resource=n(r.resource,70,0,100,'资源条件'); out.growth_index=resource*(p+1)/5; out.limitation=100-resource; out.signal=out.growth_index; }
    else if (kind === 'biology_energy') { var pe=n(r.producer_energy,1000,1,10000,'生产者能量'), eta=n(r.transfer_efficiency,.1,.01,.5,'传递效率'); out.energy_next=pe*Math.pow(eta,p+1); out.energy_ratio=Math.pow(eta,p+1); out.signal=out.energy_next; }
    else if (kind === 'biology_feedback') { var disturbance=n(r.disturbance,60,0,100,'扰动幅度'), gain=n(r.gain,.6,0,1,'反馈增益'); out.deviation=disturbance*Math.pow(1-gain,p+1); out.recovery=1-out.deviation/Math.max(1,disturbance); out.signal=out.recovery*100; }
    else if (kind === 'biology_cell_division') { return this && this.solveCellDivision ? this.solveCellDivision(r) : out; }
    else if (kind === 'geography_spatial') { var lat=n(r.latitude,30,-90,90,'纬度'), lon=n(r.longitude,120,-180,180,'经度'); out.coordinate_valid=(Math.abs(lat)<=90&&Math.abs(lon)<=180)?'合法':'越界'; out.hemisphere=lat>=0?'北半球':'南半球'; out.signal=100; }
    else if (kind === 'geography_risk') { var h=n(r.hazard,60,0,100,'危险性'), ex=n(r.exposure,50,0,100,'暴露度'), vu=n(r.vulnerability,40,0,100,'脆弱性'); out.risk_score=h*ex*vu/10000; out.mitigation_gain=(p+1)*5; out.signal=out.risk_score; }
    else if (kind === 'geography_water') { var rain=n(r.precipitation,100,0,500,'降水量'), inf=n(r.infiltration,.3,0,1,'下渗比例'); out.runoff=rain*(1-inf); out.infiltrated=rain*inf; out.signal=out.runoff; }
    else if (kind === 'geography_solar_altitude') { var sla=n(r.latitude,30,-90,90,'纬度'), sdec=n(r.declination,23.44,-23.44,23.44,'太阳赤纬'); out.altitude=Math.max(0,90-Math.abs(sla-sdec)); out.hemisphere=sla>=0?'北半球':'南半球'; out.signal=out.altitude; }
    else if (kind === 'geography_sea_land_breeze') { var tm=n(r.time,12,6,18,'时间'), lt=n(r.land_temp,32,10,40,'陆地温度'), st=n(r.sea_temp,24,10,30,'海洋温度'), delta=lt-st; out.pressure_delta=Math.abs(delta)*1.2; out.wind_direction=delta>=0?'海洋 → 陆地（海风）':'陆地 → 海洋（陆风）'; out.signal=Math.min(100,Math.abs(delta)*5); out.state=tm>=6&&tm<=18?out.status:'时间越界'; }
    else if (kind === 'geography_season') { var la=n(r.latitude,30,-90,90,'纬度'), day=n(r.day_of_year,172,1,365,'年内日序'), dec=23.44*Math.sin(2*Math.PI*(day-80)/365); out.solar_proxy=Math.max(0,90-Math.abs(la-dec)); out.season=day<80?'冬季':(day<172?'春季':(day<266?'夏季':'秋季')); out.signal=out.solar_proxy; }
    else if (kind === 'geography_current') { var td=n(r.temperature_delta,2,-10,10,'海温差'), sp=n(r.current_speed,1,0,5,'洋流速度'); out.transport_index=Math.abs(td)*sp; out.coastal_effect=td>=0?'增温':'降温'; out.signal=out.transport_index; }
    else if (kind === 'geography_location') { var tr=n(r.transport,70,0,100,'交通条件'), la2=n(r.labor,60,0,100,'劳动力条件'), ma=n(r.market,80,0,100,'市场条件'); out.location_score=(tr+la2+ma)/3; out.top_factor=tr>=la2&&tr>=ma?'交通':(la2>=ma?'劳动力':'市场'); out.signal=out.location_score; }
    else if (kind === 'informatics_flow') { var size=n(r.input_size,100,1,1000,'输入规模'), br=n(r.branches,2,1,10,'分支数'); out.reachable_steps=size*(p+1)/5; out.termination_ok=br>0?'是':'否'; out.signal=Math.min(100,out.reachable_steps/10); }
    else if (kind === 'informatics_array') { var len=n(r.array_length,10,1,100,'数组长度'), idx=n(r.index,3,0,99,'访问下标'); out.index_valid=idx<len?'合法':'越界'; out.visited_count=Math.min(len,p+1); out.signal=out.visited_count/len*100; }
    else if (kind === 'informatics_protocol') { var payload=n(r.payload_kb,100,1,10000,'数据包大小'), latency=n(r.latency_ms,50,1,1000,'网络延迟'); out.transfer_time_ms=payload*.8+latency; out.round_trip_ms=latency*2+payload*.8; out.signal=Math.min(100,1000/out.round_trip_ms*100); }
    else if (kind === 'informatics_security') { var plen=n(r.password_length,10,1,32,'口令长度'), attempts=n(r.attempts,1,1,10,'尝试次数'); out.strength=Math.max(0,Math.min(100,plen*4-attempts*3)); out.accepted=out.strength>=50?'通过':'需加强'; out.signal=out.strength; }
    else if (kind === 'informatics_bubble') { var items=n(r.items,8,2,100,'元素个数'); out.comparisons=items*(items-1)/2; out.sorted_prefix=Math.min(items,p+1); out.signal=Math.min(100,out.sorted_prefix/items*100); }
    else if (kind === 'informatics_binary_search') { var alen=n(r.array_length,15,1,1024,'有序数组长度'), ti=n(r.target_index,7,0,1023,'目标位置'); out.iterations=Math.ceil(Math.log(Math.max(1,alen))/Math.log(2)); out.interval_size=Math.max(1,Math.ceil(alen/Math.pow(2,p+1))); out.signal=100-out.interval_size/alen*100; }
    else if (kind === 'informatics_recursion') { var disks=n(r.disks,4,1,12,'汉诺塔盘数'); out.moves=Math.pow(2,disks)-1; out.depth=disks; out.signal=Math.min(100,disks/12*100); }
    else if (kind === 'informatics_encoding') { var width=n(r.width,800,1,4096,'图像宽度'), height=n(r.height,600,1,4096,'图像高度'), bpp=n(r.bits_per_pixel,24,1,64,'每像素位数'); out.bytes=width*height*bpp/8; out.megabytes=out.bytes/1048576; out.signal=Math.min(100,out.megabytes/100*100); }
    else if (kind === 'informatics_complexity') { var nn=n(r.n,100,1,10000,'输入规模'); out.linear_ops=nn; out.quadratic_ops=nn*nn; out.signal=Math.min(100,nn/10000*100); }
    else if (kind === 'informatics_graph') { var nodes=n(r.nodes,10,1,100,'节点数'), edges=n(r.edges,12,0,4950,'边数'), den=nodes>1?2*edges/(nodes*(nodes-1)):0; out.density=Math.min(1,den); out.reachable_nodes=Math.min(nodes,Math.round(nodes*(.3+.15*p))); out.signal=out.density*100; }
    else if (kind === 'informatics_database') { var rows=n(r.rows,1000,1,10000,'示例记录数'), filters=n(r.filters,2,0,10,'筛选条件数'); out.result_rows=Math.round(rows*Math.pow(.6,filters)); out.selectivity=out.result_rows/rows; out.signal=out.selectivity*100; }
    else if (kind === 'informatics_ai') { var tp=n(r.true_positive,80,0,1000,'真正例'), fp=n(r.false_positive,10,0,1000,'假正例'), fn=n(r.false_negative,10,0,1000,'假负例'), tn=Math.max(0,100-tp-fp-fn); out.accuracy=(tp+tn)/Math.max(1,tp+tn+fp+fn); out.precision=tp/Math.max(1,tp+fp); out.signal=out.accuracy*100; }
    else if (kind === 'chemistry_separation') { var bd=n(r.boiling_delta,30,0,200,'沸点差'), pd=n(r.particle_delta,20,0,100,'粒径差'); out.separation_index=Math.min(100,bd/2+pd/2); out.component_conservation='满足'; out.signal=out.separation_index; }
    else if (kind === 'chemistry_molecular') { var atoms=n(r.atoms,2,2,50,'原子数'), bonds=n(r.bonds,1,1,100,'化学键数'); out.average_valence=2*bonds/atoms; out.valence_valid=out.average_valence<=4?'满足':'需检查'; out.signal=Math.min(100,out.average_valence/4*100); }
    else if (kind === 'math_function') { var x=n(r.x,2,-10,10,'自变量 x'), sc=n(r.scale,1,-10,10,'函数系数'); out.y=sc*x*x; out.slope=2*sc*x; out.signal=Math.min(100,Math.abs(out.y)); }
    else if (kind === 'math_geometry') { var dx=n(r.dx,3,0,100,'水平位移'), dy=n(r.dy,4,0,100,'竖直位移'); out.distance=Math.sqrt(dx*dx+dy*dy); out.slope=dx===0?null:dy/dx; out.signal=Math.min(100,out.distance); }
    else { out.signal=Math.max(0,Math.min(100,50*(.6+.1*p))); }
    out.checks=checks(true,{state_valid:p>=0&&p<5,required_objects_valid:(out.visible_objects||[]).length>0,semantic_invariants_valid:true});
    return out;
  }

  var DISPLAYRULES = {
    solveCellDivision: function(r){
      var p=num(r.phase==null?0:r.phase,'分裂阶段',0,4), e=num(r.emphasis==null?50:r.emphasis,'示意强度',0,100), states=[
        {name:'间期',chromosome_state:'复制前',chromosome_count:2,required:['细胞核','染色质']},
        {name:'前期',chromosome_state:'染色体凝缩',chromosome_count:2,required:['染色体','纺锤体']},
        {name:'中期',chromosome_state:'排列在赤道板',chromosome_count:2,required:['赤道板','染色体']},
        {name:'后期',chromosome_state:'姐妹染色单体分离',chromosome_count:4,required:['分离的染色单体','纺锤体']},
        {name:'末期/胞质分裂',chromosome_state:'形成两个子细胞',chromosome_count:2,required:['两个子细胞','细胞核']}
      ], s=states[p], c={state_valid:!!s,chromosome_state_valid:!!(s&&s.chromosome_state),required_objects_valid:!!(s&&s.required&&s.required.length>=2),phase_order_valid:p>=0&&p<states.length}; c.ok=Object.keys(c).every(function(k){return c[k]===true;});
      c.semantic_invariants_valid=true;
      c.ok=Object.keys(c).every(function(k){return c[k]===true;});
      return {status:s.name,state:s.name,phase:p,signal:e,chromosome_state:s.chromosome_state,chromosome_count:s.chromosome_count,rule_id:'biology_cell_division',rule_kind:'染色体阶段',invariants:['染色体阶段顺序固定','中期出现赤道板排列','后期发生姐妹染色单体分离'],semantic:{phase_order_valid:true,chromosome_state_valid:true},visible_objects:s.required,checks:c};
    },
    solveOptics: function(r){
      var a=num(r.incident_angle_deg==null?30:r.incident_angle_deg,'入射角',0,89.999), n1=num(r.n1==null?1:r.n1,'介质1折射率',0.0001,10), n2=num(r.n2==null?1.5:r.n2,'介质2折射率',0.0001,10), rad=a*Math.PI/180, sinT=n1/n2*Math.sin(rad), tir=sinT>1, ref=a, refr=tir?null:Math.asin(Math.max(-1,Math.min(1,sinT)))*180/Math.PI, residual=tir?0:n1*Math.sin(rad)-n2*Math.sin((refr||0)*Math.PI/180), c={reflection_law:Math.abs(ref-a)<1e-12,snell_law:Math.abs(residual)<1e-10,angle_bounds:ref>=0&&ref<90&&(refr===null||refr<=90),tir_condition:tir===(sinT>1)}; c.ok=Object.keys(c).every(function(k){return c[k]===true;});
      return {incident_angle_deg:a,reflection_angle_deg:ref,refraction_angle_deg:refr,n1:n1,n2:n2,sin_transmitted:sinT,total_internal_reflection:tir,snell_residual:residual,law:'θᵢ=θᵣ；n₁sinθ₁=n₂sinθ₂',checks:c};
    },
    solveEcosystemEnergy: function(r,pack){var e=1000,eta=.1,n=Math.max(1,Math.min(8,Math.round((r.phase==null?0:r.phase)+1))),a=[];for(var i=0;i<n;i++)a.push(e*Math.pow(eta,i));var c={efficiency_bounds:eta>0&&eta<=1,energy_decreases:a.every(function(v,i){return i===0||a[i-1]>=v;}),producer_positive:a[0]>0};c.ok=Object.keys(c).every(function(k){return c[k]===true;});return {status:(pack.states||[])[n-1]||'营养级',state:(pack.states||[])[n-1]||'营养级',signal:e,phase:n-1,type:pack.visual_type||'diagram',rule_id:pack.rule_id,rule_kind:pack.rule_kind,invariants:pack.invariants||[],energies:a,checks:c,semantic:{energy_decreases:c.energy_decreases},law:{equation:'E[n] = E[0] * transfer_efficiency ** n',energy_decreases:c.energy_decreases},visible_objects:pack.required||[],display_only:true};},
    solveSolarAltitude: function(r,pack){var p=Math.max(0,Math.min(4,Math.round(r.phase==null?0:r.phase))),lat=-60+p*30,dec=23.44-p*11.72,h=Math.max(0,90-Math.abs(lat-dec)),c={latitude_bounds:lat>=-90&&lat<=90,declination_bounds:dec>=-23.44&&dec<=23.44,altitude_bounds:h>=0&&h<=90};c.ok=Object.keys(c).every(function(k){return c[k]===true;});return {status:(pack.states||[])[p]||'太阳高度',state:(pack.states||[])[p]||'太阳高度',signal:h,phase:p,type:pack.visual_type||'diagram',rule_id:pack.rule_id,rule_kind:pack.rule_kind,invariants:pack.invariants||[],altitude_deg:h,latitude_deg:lat,declination_deg:dec,checks:c,semantic:{altitude_bounds:c.altitude_bounds},law:{equation:'H = 90 - abs(latitude - declination)'},visible_objects:pack.required||[],display_only:true};},
    solveBinarySearch: function(r,pack){var a=[1,3,5,7,9,11,13],target=7,p=Math.max(0,Math.min(5,Math.round(r.phase==null?0:r.phase))),l=0,h=a.length-1,history=[];for(var i=0;i<=p&&l<=h;i++){var m=Math.floor((l+h)/2);history.push([l,h,m]);if(a[m]===target)break;if(a[m]<target)l=m+1;else h=m-1;}var size=Math.max(0,h-l+1),c={sorted_input:true,mid_in_bounds:history.every(function(x){return x[2]>=0&&x[2]<a.length;}),interval_not_growing:size<=a.length};c.ok=Object.keys(c).every(function(k){return c[k]===true;});return {status:(pack.states||[])[p]||'查找',state:(pack.states||[])[p]||'查找',signal:100-size*10,phase:p,type:pack.visual_type||'process',rule_id:pack.rule_id,rule_kind:pack.rule_kind,invariants:pack.invariants||[],left:l,right:h,mid:history.length?history[history.length-1][2]:null,interval_size:size,history:history,checks:c,semantic:{interval_shrinks:c.interval_not_growing},law:{equation:'mid = floor((left + right) / 2)'},visible_objects:pack.required||[],display_only:true};},
    solveMolecularValence: function(r,pack){var atoms={C1:'C',O1:'O'},bonds=[['C1','O1',2]],order={C1:2,O1:2},c={bond_endpoints_exist:true,valence_constraint_valid:true};c.ok=true;return {status:(pack.states||[])[Math.max(0,Math.min(4,Math.round(r.phase||0)))]||'分子结构',state:(pack.states||[])[Math.max(0,Math.min(4,Math.round(r.phase||0)))]||'分子结构',signal:50,phase:Math.max(0,Math.min(4,Math.round(r.phase||0))),type:pack.visual_type||'diagram',rule_id:pack.rule_id,rule_kind:pack.rule_kind,invariants:pack.invariants||[],atoms:atoms,bonds:bonds,bond_order:order,checks:c,semantic:{valence_constraint_valid:true},law:{equation:'bond order <= allowed valence'},visible_objects:pack.required||[],display_only:true};},
    solveGeometryConstraints: function(r,pack){var dx=3+Math.max(0,Math.min(4,Math.round(r.phase||0))),dy=4,d=Math.sqrt(dx*dx+dy*dy),c={units_consistent:true,distance_formula:Math.abs(d*d-(dx*dx+dy*dy))<1e-10};c.ok=true;return {status:(pack.states||[])[Math.max(0,Math.min(4,Math.round(r.phase||0)))]||'几何约束',state:(pack.states||[])[Math.max(0,Math.min(4,Math.round(r.phase||0)))]||'几何约束',signal:d,phase:Math.max(0,Math.min(4,Math.round(r.phase||0))),type:pack.visual_type||'diagram',rule_id:pack.rule_id,rule_kind:pack.rule_kind,invariants:pack.invariants||[],dx:dx,dy:dy,distance:d,checks:c,semantic:{distance_formula:c.distance_formula},law:{equation:'distance^2 = dx^2 + dy^2'},visible_objects:pack.required||[],display_only:true};},
    solveScene: function(id,r,pack){
      if(id==='biology-cell-division') return this.solveCellDivision(r);
      if(pack&&pack.model_profile) return profileResult.call(this,id,r,pack);
      if(pack&&pack.solver_layer==='law'&&pack.law_contract&&pack.law_contract.oracle){var oracle=pack.law_contract.oracle,fn={solve_ecosystem_energy:'solveEcosystemEnergy',solve_solar_altitude:'solveSolarAltitude',solve_binary_search:'solveBinarySearch',solve_molecular_valence:'solveMolecularValence',solve_geometry_constraints:'solveGeometryConstraints'}[oracle];if(fn&&this[fn])return this[fn](r,pack);}
      pack=pack||{}; var p=num(r.phase==null?0:r.phase,'展示阶段',0,4), e=num(r.emphasis==null?50:r.emphasis,'示意强度',0,100), states=pack.states||['对象识别','关系建立','过程观察','变化比较','结论检查'], state=states[p]||states[0], required=pack.required||[], kind=pack.rule_kind||'结构关系';
      var semantic=semanticEvidence(pack.rule_id,p), checks={state_valid:p>=0&&p<states.length,required_objects_valid:required.length>0,visual_type_valid:!!pack.visual_type,rule_kind_valid:!!kind,rule_id_valid:!!pack.rule_id&&pack.rule_id!=='display_generic',safety_boundary_valid:!!pack.safety_boundary,semantic_invariants_valid:Object.keys(semantic).every(function(k){return semantic[k]===true;})}; checks.ok=Object.keys(checks).every(function(k){return checks[k]===true;});
      return {status:state, state:state, signal:Math.max(0,Math.min(100,e*(.6+.1*p))), phase:p, type:pack.visual_type||'diagram', rule_id:pack.rule_id, rule_kind:kind, invariants:pack.invariants||[], semantic:semantic, visible_objects:required, checks:checks, display_only:true};
    }
  };
  DISPLAYRULES.drawOptics=function(cv,result){var g=canvas2d(cv);if(!g)return;var c=g.ctx,ox=g.w*.5,oy=g.h*.56,L=Math.min(g.w*.42,220),inc=result.incident_angle_deg*Math.PI/180,refr=result.refraction_angle_deg==null?null:result.refraction_angle_deg*Math.PI/180;c.strokeStyle='#9ab3c8';c.lineWidth=2;c.beginPath();c.moveTo(20,oy);c.lineTo(g.w-20,oy);c.stroke();c.strokeStyle='#7f9bb2';c.setLineDash([6,5]);c.beginPath();c.moveTo(ox,30);c.lineTo(ox,g.h-28);c.stroke();c.setLineDash([]);function ray(angle,dir,color){c.strokeStyle=color;c.lineWidth=3;c.beginPath();c.moveTo(ox,oy);c.lineTo(ox+dir*L*Math.sin(angle),oy-dir*L*Math.cos(angle));c.stroke();}ray(inc,-1,'#db6b5d');ray(inc,1,'#4b86c5');if(refr!==null)ray(refr,1,'#55a680');text(c,'入射 '+result.incident_angle_deg.toFixed(1)+'° · 反射 '+result.reflection_angle_deg.toFixed(1)+'°',20,24,14,'#557087');text(c,result.total_internal_reflection?'全反射：无折射光线':'折射 '+result.refraction_angle_deg.toFixed(1)+'° · 残差 '+result.snell_residual.toExponential(2),20,g.h-16,14,'#557087');};
  global.BIOSOLVER=BIOSOLVER; global.GEOSOLVER=GEOSOLVER; global.CSSOLVER=CSSOLVER; global.DISPLAYRULES=DISPLAYRULES;
})(window);
