from pathlib import Path
import hashlib, json, re, html, textwrap
from xml.sax.saxutils import escape
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Preformatted, KeepTogether, Flowable, CondPageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'
source_specs=[
 ('U01','competitive-research.pdf','Uploaded competitive research','uploaded prior analysis',None),
 ('U02','aicte-aph-2024-27-uploaded.pdf','Uploaded AICTE APH 2024-25 to 2026-27','V-U: content verified in supplied file','https://www.aicte.gov.in/sites/default/files/APH%20Final.pdf'),
 ('U03','seven-additions.jpeg','Uploaded seven additions','user supplied scope',None),
 ('S05','addendum-2025-26-mirrored.pdf','Combined handbook and 2025-26 addendum','V-M: mirror; issuer download and complete currency unconfirmed','https://edu-ecosys.com/AICTE-APH-26-27.pdf'),
 ('S06','addendum-2026-27-mirrored.pdf','2026-27 addendum','V-M: mirror; issuer download and complete currency unconfirmed','https://avantiscdnprodstorage.blob.core.windows.net/legalupdatedocs/52940/AICTE-issued-the-Corrigendum-regarding-the-Approval-Process-2026-27-February202026.pdf'),
]
sources=[]
for sid,name,title,status,url in source_specs:
 p=ROOT/'sources'/name
 row={'id':sid,'title':title,'local_path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'status':status,'publisher_reference_or_download_url':url,'checked_on':'2026-10-26','timezone':'Asia/Calcutta'}
 if p.suffix=='.pdf': row['pdf_pages']=len(PdfReader(p).pages)
 if sid=='S05': row['identity_note']='URL filename says 26-27; actual 2025-26 amendment appears at physical PDF pages 234-260; PoP text 257-260.'
 sources.append(row)
repos=[('Anexus5919/pramana','782d4d8127ea848798370238b622e18f19258ed2',0),('viraj-1709/aicte','0c1ab2d9faf75ba2261a5802a3e75834d5cfcc8b',1),('sathvik210508/AI-Powered-Application-Validation-Document-Authentication-Regulatory-Compliance-Platform','28173fd5d0086842b2d8aad90b447f4e313cb38e',2)]
competitors=[]
for repo,commit,num in repos:
 files=[]
 for p in sorted((ROOT/'research').glob(f'competitor-{num}-*')):
  files.append({'saved_path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 competitors.append({'repository':repo,'commit':commit,'review':'selected source and README inspection; not executed','saved_files':files})
web_sources=[
 ('S01','https://www.aicte.gov.in/','maintenance page; official approval routes unavailable'),
 ('S02','https://www.sih.gov.in/sih2026PS','timeout/access error; official brief/deadline not certified'),
 ('S03','https://zaidsayyed.in/tools/sih-problem-statements/sih26261','accessible secondary mirror; working brief decomposition'),
 ('S04','https://www.linkedin.com/posts/aicteindia_addendumcorrigendum-2025-26-for-the-approval-activity-7267763906738032641-d-Nr','AICTE announcement; existence of 2025-26 addendum'),
 ('S07','https://www.ccet.ac.in/pdf/auditreports/AICTE/Deficiency%20Report%202025-26.PDF','AICTE-generated report on institution host; portal baseline'),
 ('S08d','https://github.com/sohamramshette/SIH11','repository layout and README only; no runtime execution'),
 ('S08e','https://github.com/nonutsayan/CipherCore-verify','README and repository layout; hosted demo unavailable; claims unvalidated'),
 ('S10','https://www.digilocker.gov.in/web/data-exchange','official integration context; project access not established'),
 ('S11','https://entity.digilocker.gov.in/','official organization-document platform; specific coverage not established'),
 ('S11-resources','https://entity.digilocker.gov.in/web/resources','requester resources indexed; API entitlement not established'),
 ('S12-root','https://cca.gov.in/root_certificate.html','official root certificate publication'),
 ('S12-guidance','https://cca.gov.in/sites/files/pdf/guidelines/CCA-ESAIG.pdf','official verification guidance; no product signature checks run'),
 ('S13','https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/overview?view=doc-intel-4.0.0','primary product documentation; no benchmark comparison'),
 ('S14','https://docs.aws.amazon.com/textract/latest/dg/what-is.html','primary product documentation; no benchmark comparison'),
 ('S15-rules','https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf','official Gazette; phased commencement checked at English PDF page24'),
 ('S15-index','https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digital-Personal-Data-Protection-Rules-2025','official index lists rules, corrigendum and enforcement timeline; full legal applicability not certified'),
 ('S16','https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf','primary directions; deployment applicability requires mapping'),
 ('S16-FAQ','https://www.cert-in.org.in/PDF/FAQs_on_CyberSecurityDirections_May2022.pdf','primary FAQ for incident criteria')]
manifest={'research_cutoff':'2026-10-26','timezone':'Asia/Calcutta','purpose':'Source provenance and verification limits for proposed AICTE PS26261 specification v3.0','sources':sources,'web_sources':[{'id':sid,'url':url,'review_status':status,'checked_on':'2026-10-26'} for sid,url,status in web_sources],'competitors':competitors,'limitations':['AICTE approval-cycle pages and official SIH route unavailable during research.','Complete current circular set not certified.','Mirrored copies not authenticated as identical to current publisher bytes.','No team product implementation or benchmark was audited.']}
(OUT/'AICTE_PS26261_Source_Register.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')

hashes={s['id']:s['sha256'] for s in sources}
def rule(rid,sid,pdf,printed,clause,content,interpretation='REQUIRES_AUTHORIZED_REVIEW'):
 return {'rule_id':rid,'source_id':sid,'source_sha256':hashes[sid],'pdf_page':pdf,'printed_page':printed,'clause':clause,'content_summary':content,'content_status':'V-U' if sid=='U02' else 'V-M','interpretation_state':interpretation,'publication_state':'DRAFT','production_enabled':False,'adverse_action_allowed':False}
rules=[
 rule('DOC.EOA.AFFIDAVIT_2','U02',97,81,'Annexure 2.1(i)',{'e_stamp_inr':100,'digital_signature':'Chairman/Secretary','sworn_before':['First Class Judicial Magistrate','Notary','Oath Commissioner']}),
 rule('DOC.STRUCTURAL.TRIGGER','U02',73,57,'6.17(h)',{'age_basis':'Completion Certificate issue date','age_years':30,'issuer':'registered Structural Engineer','validity_years':5}),
 rule('DOC.GOVERNMENT.ALTERNATIVE','U02',97,81,'Annexure 2.1 preamble',{'age_years':50,'condition':'Specified government-built older building; original documents unavailable; competent-authority letter','blanket_safety_exemption':False}),
 rule('DOC.FIRE.VALIDITY','U02',73,57,'6.17(i)',{'requirement':'valid Fire Safety Certificate from competent authority','universal_lifetime_years':None}),
 rule('AUTHORITIES.ANNEXURE_14','U02',179,163,'Annexure 14',{'columns':['land use','site plan','building plan','occupation certificate'],'is_fire_authority_directory':False}),
 rule('INFRA.COMPUTERS.DEPARTMENT','U02',108,92,'Annexure 4.1 note 10',{'minimum_computers':20,'scope':'separate computer laboratory per department'}),
 rule('INFRA.PRINTERS','U02',108,92,'Annexure 4.1 note 3',{'minimum_fraction_of_pcs_laptops':0.05,'rounding':'requires approved operational policy'}),
 rule('INFRA.PLOTTER','U02',108,92,'Annexure 4.1 note 4',{'scope':'Planning','minimum':1,'type':'A1 size colour printer/plotter'}),
 rule('INFRA.BANDWIDTH','U02',108,92,'Annexure 4.1 note 5',{'tiers_mbps':[{'max':300,'minimum':100},{'min':301,'max':600,'minimum':300},{'min':601,'max':900,'minimum':500},{'min':901,'minimum':1000}],'transcription_note':'Source prints 1Gbpa for highest tier; preserve normalized interpretation'}),
 rule('FACULTY.UG.RATIOS','U02',111,95,'Annexure 5.2',{'engineering':20,'planning':16,'arts_crafts':15,'design':15,'hmct':20,'computer_applications':25,'management':25,'S':'sum of approved student intake for all years'}),
 rule('FACULTY.PG.RATIOS','U02',112,96,'Annexure 5.3',{'engineering':15,'planning':10,'arts_crafts':15,'design':15,'hmct':12,'MCA':20,'MBA_PGDM':20}),
 rule('FACULTY.CADRE.AMBIGUITY','U02',111,95,'Annexure 5.1-5.2',{'issue':'Printed component expressions and total do not reconcile with separately listed Principal/HOD. Uploaded UG Professor expression does not show minus one.','action':'NOT_EVALUABLE; approved interpretation required'},'INTERPRETATION_PENDING'),
 rule('FACULTY.LOW_ADMISSION','U02',112,96,'Annexure 5.3 following table',{'average_admission_max_fraction':0.5,'reference_years':3,'faculty_reduction_fraction':0.25,'scope_and_rounding':'pending approved interpretation'}),
 rule('DISCLOSURE.WEBSITE','U02',196,180,'Annexure 18',{'requirement':'public mandatory disclosure','issuer_authentication_evidence':False}),
 rule('VIDEO.WEBSITE.SHORT','U02',200,184,'Annexure 18.15(xviii)',{'minimum_minutes':1,'maximum_minutes':2,'scope':'website infrastructure/facilities disclosure'}),
 rule('VIDEO.EVC.CONTEXTUAL','U02',24,8,'1.9(f)-(g)',{'minimum_minutes':30,'scope':'specified EVC contexts; not every upload'}),
 rule('WORKFLOW.RESCRUTINY','U02',23,7,'1.8(f)-(g)',{'scope':'deficiencies pointed out by Scrutiny Committee','unrestricted_postsubmission_edit':False}),
 rule('FACULTY.POP.2025','S05',259,22,'Revised Annexure 5',{'programme':'Engineering and Technology','maximum_percentage':20,'women_reservation_wording_percentage':5,'reservation_denominator_rounding':'pending approved interpretation'}),
 rule('FACULTY.BASE_CLAUSE_DELETED','S05',257,20,'6.14(d)(iii)',{'operation':'delete specified subclause','all_programme_adjunct_abolition_established':False}),
 rule('SEATS.INTERNATIONAL.2026','S06',7,6,'2.9 modified; continues PDF8',{'engineering_diploma_ug_percent':15,'engineering_pg_percent':25,'other_listed_programmes_percent':25,'other_conditions':'must be evaluated separately'}),
 rule('CATEGORY.BBA_BMS_BCA.2026','S06',3,2,'1.3.3(b)',{'textual_change':'Non-Technical -> Technical','full_approval_scope':'unresolved; require circulars and regulatory interpretation'},'INTERPRETATION_PENDING'),
 rule('ELP.50_PERCENT.CONFLICT','S06',15,14,'Item41 versus concept note PDF20',{'issue':'table says minimum 50%; concept note says up to 50%','action':'do not choose silently'},'INTERPRETATION_PENDING')
]
(OUT/'AICTE_PS26261_Rule_Evidence_Register.json').write_text(json.dumps({'status':'proposed seed register; not deployable regulatory code','as_of':'2026-10-26','rules':rules},indent=2,ensure_ascii=False),encoding='utf-8')

# A readable, link-preserving PDF rendition of the complete Markdown report.
fontdir=Path('C:/Windows/Fonts')
for name,file in [('Body','segoeui.ttf'),('BodyBold','segoeuib.ttf'),('BodyItalic','segoeuii.ttf'),('Mono','consola.ttf')]:
 pdfmetrics.registerFont(TTFont(name,str(fontdir/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='BodyItalic',boldItalic='BodyBold')
NAVY=colors.HexColor('#15324F'); TEAL=colors.HexColor('#087E8B'); INK=colors.HexColor('#243648'); LIGHT=colors.HexColor('#EEF4F8')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Text',fontName='Body',fontSize=9.2,leading=13,spaceAfter=7,textColor=INK))
styles.add(ParagraphStyle(name='Chapter',fontName='BodyBold',fontSize=15,leading=19,spaceBefore=17,spaceAfter=9,textColor=NAVY,keepWithNext=True))
styles.add(ParagraphStyle(name='Sub',fontName='BodyBold',fontSize=11.2,leading=15,spaceBefore=11,spaceAfter=7,textColor=TEAL,keepWithNext=True))
styles.add(ParagraphStyle(name='Cell',fontName='Body',fontSize=8,leading=10.6,textColor=INK))
styles.add(ParagraphStyle(name='CellHead',fontName='BodyBold',fontSize=8,leading=10.6,textColor=colors.white))
styles.add(ParagraphStyle(name='BulletText',parent=styles['Text'],leftIndent=12,firstLineIndent=-9))
styles.add(ParagraphStyle(name='CoverTitle',fontName='BodyBold',fontSize=29,leading=35,textColor=NAVY,spaceAfter=18))
styles.add(ParagraphStyle(name='CoverSub',fontName='Body',fontSize=14,leading=20,textColor=TEAL,spaceAfter=20))
styles.add(ParagraphStyle(name='Small',fontName='Body',fontSize=8,leading=11,textColor=INK,spaceAfter=8))

def inline(s):
 links=[]
 def save_link(m):
  links.append((m.group(1),m.group(2)))
  return f'LINKTOKEN{len(links)-1}END'
 s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',save_link,s)
 s=escape(s)
 s=re.sub(r'`([^`]+)`',lambda m:'<font name="Mono" size="8">'+m.group(1)+'</font>',s)
 s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
 for i,(label,url) in enumerate(links):
  s=s.replace(f'LINKTOKEN{i}END',f'<link href="{html.escape(url,quote=True)}" color="#087E8B">{escape(label)}</link>')
 return s

class ReportDoc(SimpleDocTemplate):
 def afterFlowable(self,f):
  if isinstance(f,Paragraph) and f.style.name=='Chapter':
   key='chapter_'+str(len(self.chapter_pages))
   self.canv.bookmarkPage(key)
   self.canv.addOutlineEntry(f.getPlainText(),key,level=0,closed=False)
   self.chapter_pages.append({'heading':f.getPlainText(),'page':self.page})

class NumberedCanvas(canvas.Canvas):
 def __init__(self,*a,**kw): super().__init__(*a,**kw); self.saved=[]
 def showPage(self): self.saved.append(dict(self.__dict__)); self._startPage()
 def save(self):
  count=len(self.saved)
  for state in self.saved:
   self.__dict__.update(state)
   self.setFillColor(NAVY); self.setFont('Body',8)
   self.drawString(42,27,'AICTE PS26261  |  Research + proposed specification  |  26 Oct 2026')
   self.drawRightString(A4[0]-42,27,f'{self._pageNumber} / {count}')
   if self._pageNumber>1:
    self.setStrokeColor(colors.HexColor('#D8E5EC')); self.line(42,A4[1]-35,A4[0]-42,A4[1]-35)
    self.setFillColor(TEAL); self.setFont('Body',8); self.drawString(42,A4[1]-27,'EVIDENCE AND COMPLIANCE WORKBENCH  /  v3.0')
   canvas.Canvas.showPage(self)
  canvas.Canvas.save(self)

class Architecture(Flowable):
 def __init__(self): super().__init__(); self.width=A4[0]-84; self.height=186
 def draw(self):
  c=self.canv; gap=18; bw=(self.width-gap*2)/3; bh=55
  def box(col,y,title,body):
   x=col*(bw+gap); c.setFillColor(LIGHT); c.setStrokeColor(colors.HexColor('#B7D0DA')); c.roundRect(x,y,bw,bh,5,fill=1,stroke=1)
   c.setFillColor(NAVY); c.setFont('BodyBold',9); c.drawString(x+9,y+bh-16,title)
   c.setFont('Body',8)
   for n,l in enumerate(body):c.drawString(x+9,y+bh-31-11*n,l)
  def arrow(x1,y1,x2,y2):
   import math
   c.setStrokeColor(TEAL); c.setLineWidth(1); c.line(x1,y1,x2,y2)
   angle=math.atan2(y2-y1,x2-x1)
   for d in [-.45,.45]: c.line(x2,y2,x2-5*math.cos(angle+d),y2-5*math.sin(angle+d))
  box(0,117,'Evidence intake',['Authorize and quarantine','Preserve originals'])
  box(1,117,'Extract and reconcile',['Version facts and regions','Record source observations'])
  box(2,117,'Frozen run inputs',['Facts + evidence versions','Source response snapshots'])
  box(0,22,'Approved rule release',['Source + applicability review','Separate author / approver'])
  box(1,22,'Deterministic evaluation',['Findings + uncertainty','Pinned rules and facts'])
  box(2,22,'Authorized review',['Scoped response + version diff','Reports, tasks and audit'])
  arrow(bw,144,bw+gap,144); arrow(2*bw+gap,144,2*(bw+gap),144)
  arrow(bw,49,bw+gap,49); arrow(2*bw+gap,49,2*(bw+gap),49)
  arrow(2*(bw+gap)+bw/2,117,2*(bw+gap)+bw/2,95)
  arrow(2*(bw+gap)+bw/2,95,bw+gap+bw/2,77)
  c.setFont('BodyItalic',8); c.setFillColor(TEAL); c.drawString(0,3,'Proposed architecture. Statutory scrutiny, inspection and decisions remain with AICTE.')

story=[]
story.append(Spacer(1,34))
story.append(Paragraph('AICTE PS26261',styles['CoverSub']))
story.append(Paragraph('A governed evidence and rectification workbench',styles['CoverTitle']))
story.append(Paragraph('Revised solution context, technical specification and differentiation strategy',styles['CoverSub']))
story.append(Paragraph('26 October 2026  |  Version 3.0',styles['Text']))
story.append(Spacer(1,16))
for title,body in [
 ('1  Apply the right rule','Sourced amendments, explicit applicability, separate approvers and preserved historical evaluations.'),
 ('2  Make correction reviewable','Permitted response windows, evidence versions, field diffs and reassessment with an audit trail.'),
 ('3  Show what remains uncertain','Completeness, source verification and forensic concerns remain separate. Authority stays with AICTE.')]:
 story.append(Paragraph(title,styles['Sub'])); story.append(Paragraph(body,styles['Text']))
story.append(Spacer(1,20))
story.append(Paragraph('<b>Research findings and proposed design are explicitly distinguished.</b> No team product implementation, live government integration or product benchmark is claimed.',styles['Text']))
story.append(Paragraph('Source note: uploaded documents were inspected. Selected annual amendment text was checked on public mirrors. Current AICTE approval pages were unavailable, so complete regulatory currency is not certified.',styles['Small']))
story.append(PageBreak())
story.append(Paragraph('Reading guide',styles['Chapter']))
for label,desc in [('Decision and evidence','Sections 1-3: corrected facts, source limits, faculty ambiguity and scoped amendments.'),('Solution and specification','Sections 4-9: user context, requirements, status model, architecture and all seven additions.'),('Strategy and delivery','Sections 10-12: competitor source evidence, priorities and a five-minute demonstration.'),('Evaluation and compliance','Sections 13-15: measured-versus-target reporting, security, privacy and claims.'),('Audit references','Appendices: all 32 earlier corrections and source links.')]:
 story.append(Paragraph('<b>'+label+'</b> - '+desc,styles['Text']))
story.append(Spacer(1,12)); story.append(Paragraph('Evidence legend',styles['Sub']))
story.append(Paragraph('V-U: uploaded source checked. V-P: primary source checked. V-M: mirrored document text checked. C-S: competitor code inspected. C-R: competitor claim only. P: proposed. O: unresolved.',styles['Text']))
story.append(Paragraph('Use the PDF bookmarks to jump to any chapter. The companion Markdown contains the same full report for editing. The source register preserves file hashes and inspected commits; the rule register is a draft evidence catalogue with production enforcement disabled.',styles['Text']))
story.append(Spacer(1,12)); story.append(Paragraph('System boundaries',styles['Sub'])); story.append(Architecture())
story.append(PageBreak())

lines=(OUT/'AICTE_PS26261_Revised_Solution_Context.md').read_text(encoding='utf-8').splitlines()
i=0
width=A4[0]-84
while i<len(lines):
 line=lines[i]
 if line.startswith('# '): i+=1; continue
 if not line.strip(): i+=1; continue
 if line.startswith('```'):
  i+=1; code=[]
  while i<len(lines) and not lines[i].startswith('```'):
   code.extend(textwrap.wrap(lines[i],width=93,replace_whitespace=False,drop_whitespace=False) or [' ']); i+=1
  story.append(Preformatted('\n'.join(code),ParagraphStyle('Code',fontName='Mono',fontSize=7.3,leading=10,backColor=LIGHT,borderPadding=8,spaceAfter=10)))
  i+=1; continue
 if line.startswith('### '): story.append(Paragraph(inline(line[4:]),styles['Sub'])); i+=1; continue
 if line.startswith('## '):
  nxt=next((s for s in lines[i+1:] if s.strip()),'')
  if nxt.startswith('|'): story.append(CondPageBreak(125))
  story.append(Paragraph(inline(line[3:]),styles['Chapter']))
  if nxt.startswith('|'): story.append(Spacer(1,1))
  i+=1; continue
 if line.startswith('|'):
  rows=[]
  while i<len(lines) and lines[i].startswith('|'):
   cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
   if not all(re.fullmatch(r':?-+:?',c.replace(' ','')) for c in cells): rows.append(cells)
   i+=1
  n=max(map(len,rows)); rows=[r+['']*(n-len(r)) for r in rows]
  if n==2: ratios=[.12,.88]
  elif n==3: ratios=[.22,.28,.50]
  elif n==4: ratios=[.20,.28,.24,.28]
  else: ratios=[1/n]*n
  data=[[Paragraph(inline(c),styles['CellHead'] if j==0 else styles['Cell']) for c in row] for j,row in enumerate(rows)]
  t=Table(data,colWidths=[width*r for r in ratios],repeatRows=1,hAlign='LEFT')
  t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),('LINEBELOW',(0,0),(-1,0),.5,TEAL),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#D8E5EC'))]))
  story.extend([t,Spacer(1,9)]); continue
 if line.startswith('- ') or re.match(r'^\d+\. ',line):
  story.append(Paragraph(inline(line),styles['BulletText'])); i+=1; continue
 p=[line];i+=1
 while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|- |\d+\. )',lines[i]): p.append(lines[i]);i+=1
 story.append(Paragraph(inline(' '.join(p)),styles['Text']))

pdf=OUT/'AICTE_PS26261_Revised_Solution_Context.pdf'
doc=ReportDoc(str(pdf),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=49,bottomMargin=45,title='AICTE PS26261 - Revised Solution Context and Build Specification',author='Research and proposed specification',allowSplitting=True)
doc.chapter_pages=[]
doc.build(story,canvasmaker=NumberedCanvas)
(ROOT/'research/pdf_chapter_pages.json').write_text(json.dumps(doc.chapter_pages,indent=2),encoding='utf-8')
print(json.dumps({'pdf':str(pdf),'pages':len(PdfReader(pdf).pages),'markdown_words':len((OUT/'AICTE_PS26261_Revised_Solution_Context.md').read_text(encoding='utf-8').split()),'sources':len(sources),'draft_rule_records':len(rules)},indent=2))
